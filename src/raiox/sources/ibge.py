"""IBGE — UFs (sigla, nome, região) e malha das UFs em GeoJSON."""

from __future__ import annotations

import json
from typing import Any

import polars as pl

from raiox.bronze import write_bronze
from raiox.config import Settings
from raiox.http import HttpClient, check_contract
from raiox.logs import logger

SOURCE = "ibge"


def _round_coords(obj: Any, nd: int) -> Any:
    if isinstance(obj, list):
        if obj and isinstance(obj[0], (int, float)):
            return [round(v, nd) for v in obj]
        return [_round_coords(o, nd) for o in obj]
    return obj


def _ring_area(ring: list) -> float:
    """Área com sinal (fórmula do laço); > 0 = anti-horário em lon/lat."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:], strict=False)) / 2


def rewind_for_d3(geometry: dict) -> dict:
    """Orienta os anéis no padrão do d3/plotly (exterior horário, buracos anti-horários).

    A malha do IBGE segue o RFC 7946 (exterior anti-horário); sem isso o plotly pinta
    "o mundo menos o estado" e o mapa vira um retângulo.
    """

    def fix(poly: list) -> list:
        out = []
        for i, ring in enumerate(poly):
            ccw = _ring_area(ring) > 0
            want_cw = i == 0
            out.append(
                list(reversed(ring)) if (ccw and want_cw) or (not ccw and not want_cw) else ring
            )
        return out

    if geometry["type"] == "Polygon":
        geometry["coordinates"] = fix(geometry["coordinates"])
    elif geometry["type"] == "MultiPolygon":
        geometry["coordinates"] = [fix(p) for p in geometry["coordinates"]]
    return geometry


def ingest(settings: Settings, client: HttpClient) -> dict[str, int]:
    cfg = settings.ibge
    ref = settings.path("reference")
    ref.mkdir(parents=True, exist_ok=True)

    env = client.get_json(cfg.states_url, key="estados")
    ufs = pl.DataFrame()
    if env is not None:
        rows = env["body"]
        check_contract("ibge.estados", rows[0], {"id", "sigla", "nome", "regiao"}, {"id", "sigla"})
        ufs = pl.DataFrame(
            [
                {
                    "codigo_ibge": int(r["id"]),
                    "uf": r["sigla"],
                    "nome": r["nome"],
                    "regiao_sigla": r["regiao"]["sigla"],
                    "regiao": r["regiao"]["nome"],
                }
                for r in rows
            ]
        ).sort("codigo_ibge")
        write_bronze(settings, "ufs", client.snapshot, ufs, SOURCE, env["meta"]["fetched_at"])
        if not settings.offline:
            ufs.write_csv(ref / "ufs.csv")

    geo_env = client.get_json(cfg.geojson_url, key="malha_uf")
    if geo_env is not None and ufs.height and not settings.offline:
        geo = geo_env["body"]
        code_to_uf = dict(zip(ufs["codigo_ibge"].to_list(), ufs["uf"].to_list(), strict=True))
        code_to_nome = dict(zip(ufs["codigo_ibge"].to_list(), ufs["nome"].to_list(), strict=True))
        for feat in geo["features"]:
            code = int(feat["properties"]["codarea"])
            feat["properties"]["uf"] = code_to_uf.get(code)
            feat["properties"]["nome"] = code_to_nome.get(code)
            feat["id"] = code_to_uf.get(code)
            feat["geometry"] = rewind_for_d3(feat["geometry"])
        text = json.dumps(geo, ensure_ascii=False, separators=(",", ":"))
        nd = 4
        while len(text.encode()) > cfg.geojson_max_bytes and nd > 1:
            nd -= 1
            for feat in geo["features"]:
                feat["geometry"]["coordinates"] = _round_coords(feat["geometry"]["coordinates"], nd)
            text = json.dumps(geo, ensure_ascii=False, separators=(",", ":"))
        (ref / "uf.geojson").write_text(text, encoding="utf-8")
        logger.info("IBGE: GeoJSON das UFs salvo ({} KB)", len(text.encode()) // 1024)
    return {"ufs": ufs.height}
