"""ComexStat (MDIC) — importação e exportação por NCM.

POST https://api-comexstat.mdic.gov.br/general (confirmado na Fase 1).
Valores numéricos vêm como texto ("2489074"); a conversão acontece na bronze.
Fallbacks (seção 5.1-B): pacote `comexpy` e base bruta em CSV do MDIC — ver
docs/FONTES.md. A implementação própria funcionou na Fase 1, então os fallbacks
ficam documentados e não são dependência do projeto.
"""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

import polars as pl

from raiox.bronze import frame_from_records, write_bronze
from raiox.config import Settings
from raiox.http import HttpClient, check_contract
from raiox.logs import logger

SOURCE = "comex"

EXPECTED_FIELDS = {
    "coNcm",
    "year",
    "monthNumber",
    "ncm",
    "country",
    "state",
    "metricFOB",
    "metricKG",
    "metricStatistic",
}

COMEX_SCHEMA: dict[str, pl.DataType] = {
    "coNcm": pl.String,
    "year": pl.Int64,
    "monthNumber": pl.Int64,
    "ncm": pl.String,
    "country": pl.String,
    "state": pl.String,
    "metricFOB": pl.Float64,
    "metricKG": pl.Float64,
    "metricStatistic": pl.Float64,
    "metricFreight": pl.Float64,
    "metricInsurance": pl.Float64,
    "metricCIF": pl.Float64,
}

AUX_ENDPOINTS = {
    "filters": "/general/filters",
    "details": "/general/details",
    "metrics": "/general/metrics",
    "dates_updated": "/general/dates/updated",
    "ncm": "/tables/ncm",
    "countries": "/tables/countries",
}


class ComexSource:
    def __init__(self, settings: Settings, client: HttpClient):
        self.s = settings
        self.c = client
        self.cfg = settings.comex

    def url(self, path: str) -> str:
        return self.cfg.base_url.rstrip("/") + path

    def last_update(self) -> tuple[int, int]:
        env = self.c.get_json(self.url(AUX_ENDPOINTS["dates_updated"]), key="aux_dates_updated")
        if env is None:
            today = date.today()
            return today.year, today.month
        d = env["body"]["data"]
        return int(d["year"]), int(d["monthNumber"])

    def aux(self) -> dict[str, Any]:
        out = {}
        for name, path in AUX_ENDPOINTS.items():
            env = self.c.get_json(self.url(path), key=f"aux_{name}")
            out[name] = None if env is None else env["body"]
        return out

    def query(
        self, flow: str, year: int, last_month: int, ncms: list[str], chunk_id: int
    ) -> list[dict[str, Any]] | None:
        metrics = self.cfg.metrics_import if flow == "import" else self.cfg.metrics_export
        body = {
            "flow": flow,
            "monthDetail": True,
            "period": {"from": f"{year}-01", "to": f"{year}-{last_month:02d}"},
            "filters": [{"filter": "ncm", "values": ncms}],
            "details": self.cfg.details,
            "metrics": metrics,
        }
        key = f"general_{flow}_{year}_c{chunk_id:02d}"
        cached = self.c.store.exists(key)
        env = self.c.post_json(self.url("/general"), key=key, body=body)
        if not cached and not self.s.offline:
            time.sleep(self.cfg.pause_s)
        if env is None:
            return None
        payload = env["body"]
        if not payload.get("success", True):
            logger.error("ComexStat {} {}: {}", flow, year, payload.get("message"))
            return None
        rows = payload.get("data", {}).get("list", [])
        if rows:
            check_contract(
                f"comex.general.{flow}", rows[0], EXPECTED_FIELDS, {"coNcm", "year", "metricFOB"}
            )
        return rows

    def ingest(self) -> dict[str, int]:
        last_year, last_month = self.last_update()
        ncms = [n.ncm for n in self.cfg.ncms]
        size = self.cfg.ncms_per_request
        chunks = [ncms[i : i + size] for i in range(0, len(ncms), size)]
        counts: dict[str, int] = {}
        for flow in self.cfg.flows:
            total = 0
            for year in range(self.cfg.start_year, last_year + 1):
                lm = last_month if year == last_year else 12
                for ci, chunk in enumerate(chunks):
                    rows = self.query(flow, year, lm, chunk, ci)
                    if rows is None:
                        if not self.s.offline:
                            logger.warning("ComexStat {} {} chunk {}: sem dados", flow, year, ci)
                        continue
                    total += len(rows)
            counts[flow] = total
            logger.info("ComexStat {}: {} linhas", flow, total)
        return counts


def build_bronze(settings: Settings, client: HttpClient) -> dict[str, int]:
    out = {}
    for flow, table in (("import", "comex_import"), ("export", "comex_export")):
        records: list[dict[str, Any]] = []
        fetched = None
        for _, env in client.store.iter_envelopes(f"general_{flow}_"):
            fetched = max(fetched or "", env["meta"]["fetched_at"])
            records.extend(env["body"].get("data", {}).get("list", []))
        df = frame_from_records(records, COMEX_SCHEMA)
        if df.height:
            write_bronze(settings, table, client.snapshot, df, SOURCE, fetched)
        out[flow] = df.height
    return out


def save_reference(settings: Settings, client: HttpClient) -> None:
    """Salva auxiliares do ComexStat em data/reference (NCM do cap. 90, países, métricas)."""
    src = ComexSource(settings, client)
    aux = src.aux()
    ref = settings.path("reference")
    ref.mkdir(parents=True, exist_ok=True)
    small = {
        k: v for k, v in aux.items() if k in {"filters", "details", "metrics", "dates_updated"}
    }
    (ref / "comex_auxiliares.json").write_text(
        json.dumps(small, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    if aux.get("ncm"):
        lst = aux["ncm"]["data"]["list"]
        cap90 = [r for r in lst if str(r.get("coNcm", "")).startswith(("9021", "9018"))]
        (ref / "comex_ncm_9018_9021.json").write_text(
            json.dumps(cap90, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    if aux.get("countries"):
        (ref / "comex_paises.json").write_text(
            json.dumps(aux["countries"], ensure_ascii=False), encoding="utf-8"
        )


def ingest(settings: Settings, client: HttpClient) -> dict[str, int]:
    src = ComexSource(settings, client)
    counts = src.ingest()
    if not settings.offline:
        save_reference(settings, client)
    build_bronze(settings, client)
    return counts
