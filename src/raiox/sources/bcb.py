"""Banco Central — SGS: IPCA mensal (433) e dólar PTAX venda média mensal (3698).

Séries diárias têm limite de janela: a consulta é paginada em blocos de até
`window_years` anos. Fallback do câmbio: série diária 1 agregada por mês.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl

from raiox.bronze import write_bronze
from raiox.config import Settings
from raiox.http import HttpClient, check_contract
from raiox.logs import logger

SOURCE = "bcb"


def _windows(start: date, end: date, years: int) -> list[tuple[date, date]]:
    out = []
    cur = start
    while cur <= end:
        nxt = date(min(cur.year + years, 9999), 1, 1)
        stop = min(date(nxt.year - 1, 12, 31), end)
        out.append((cur, stop))
        cur = date(stop.year + 1, 1, 1)
    return out


def fetch_series(settings: Settings, client: HttpClient, code: int) -> list[dict[str, Any]]:
    cfg = settings.bcb
    start = date.fromisoformat(cfg.start_date)
    end = date.today()
    rows: list[dict[str, Any]] = []
    for w0, w1 in _windows(start, end, cfg.window_years):
        env = client.get_json(
            cfg.base_url.format(code=code),
            key=f"sgs_{code}_{w0.year}",
            params={
                "formato": "json",
                "dataInicial": w0.strftime("%d/%m/%Y"),
                "dataFinal": w1.strftime("%d/%m/%Y"),
            },
        )
        if env is None:
            continue
        body = env["body"]
        if isinstance(body, list) and body:
            check_contract(f"bcb.sgs.{code}", body[0], {"data", "valor"}, {"data", "valor"})
            rows.extend(body)
    return rows


def _to_frame(rows: list[dict[str, Any]]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(schema={"data": pl.Date, "valor": pl.Float64})
    return (
        pl.DataFrame(rows)
        .with_columns(
            pl.col("data").str.strptime(pl.Date, "%d/%m/%Y"),
            pl.col("valor").cast(pl.Float64, strict=False),
        )
        .unique(subset=["data"])
        .sort("data")
    )


def ingest(settings: Settings, client: HttpClient) -> dict[str, int]:
    cfg = settings.bcb
    ipca = _to_frame(fetch_series(settings, client, cfg.ipca_series))
    fx = _to_frame(fetch_series(settings, client, cfg.fx_series))
    fx_source = f"sgs_{cfg.fx_series}"
    if fx.height == 0:
        logger.warning(
            "Câmbio {} indisponível; usando série diária {} agregada",
            cfg.fx_series,
            cfg.fx_fallback_daily_series,
        )
        daily = _to_frame(fetch_series(settings, client, cfg.fx_fallback_daily_series))
        fx = (
            daily.with_columns(pl.col("data").dt.truncate("1mo"))
            .group_by("data")
            .agg(pl.col("valor").mean())
            .sort("data")
        )
        fx_source = f"sgs_{cfg.fx_fallback_daily_series}_media_mensal"
    fetched = None
    for _, env in client.store.iter_envelopes("sgs_"):
        fetched = max(fetched or "", env["meta"]["fetched_at"])
    if ipca.height:
        write_bronze(
            settings,
            "ipca",
            client.snapshot,
            ipca.with_columns(pl.lit(cfg.ipca_series).alias("serie")),
            SOURCE,
            fetched,
        )
    if fx.height:
        write_bronze(
            settings,
            "cambio",
            client.snapshot,
            fx.with_columns(pl.lit(fx_source).alias("serie")),
            SOURCE,
            fetched,
        )
    logger.info("BCB: IPCA {} meses, câmbio {} meses ({})", ipca.height, fx.height, fx_source)
    return {"ipca": ipca.height, "cambio": fx.height}
