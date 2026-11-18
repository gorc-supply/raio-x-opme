"""Itens de contratações PNCP (Lei 14.133) via API do Compras.gov.br.

Endpoint: GET /modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133
Filtros: codItemCatalogo + janela obrigatória dataInclusaoPncpInicial/Final.
Na Fase 1 respondeu 504/timeout mesmo com janela de 1 mês. Desligado por padrão
(`complementary.pncp_itens.enabled: false`); quando a API voltar, este cliente
consulta em janelas mensais e grava a bronze `pncp_itens`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from raiox.bronze import frame_from_records, write_bronze
from raiox.config import Settings, load_catalog
from raiox.http import HttpClient
from raiox.logs import logger

SOURCE = "pncp"


def _windows(start: date, end: date, days: int) -> list[tuple[date, date]]:
    out = []
    cur = start
    while cur <= end:
        stop = min(cur + timedelta(days=days - 1), end)
        out.append((cur, stop))
        cur = stop + timedelta(days=1)
    return out


def ingest(settings: Settings, client: HttpClient) -> dict[str, Any]:
    cfg = settings.compras
    days = int(settings.complementary.pncp_itens.get("window_days", 31))
    end = date.today()
    start = date(end.year - 2, end.month, 1)
    records: list[dict[str, Any]] = []
    for item in load_catalog(settings):
        code = int(item["codigo_catmat"])
        for w0, w1 in _windows(start, end, days):
            for env in client.paginate(
                cfg.base_url + cfg.pncp_items_path,
                {
                    "codItemCatalogo": code,
                    "dataInclusaoPncpInicial": w0.isoformat(),
                    "dataInclusaoPncpFinal": w1.isoformat(),
                },
                f"pncp_{code}_{w0:%Y%m%d}",
                cfg.page_size,
            ):
                records.extend(env["body"].get("resultado", []))
    logger.info("PNCP itens: {} registros", len(records))
    if records:
        write_bronze(
            settings, "pncp_itens", client.snapshot, frame_from_records(records, {}), SOURCE, None
        )
    return {"registros": len(records)}
