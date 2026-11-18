"""Banco de Preços em Saúde (BPS / Ministério da Saúde) — bases anuais compiladas.

Verificado na Fase 5.6 (18/11/2026): os links `/view` da página levam a
`/@@download/file`, que responde 200 a GET (HEAD dá 403). Os arquivos são XLSX
(não CSV): 2023–2024 com abas por ano, cabeçalho na 2ª linha, colunas
`Código BR` (CATMAT), `Descrição CATMAT`, `UF`, `Unidade Fornecimento`,
`Qtd Itens Comprados`, `Preço Unitário` etc.

Resultado: nenhum dos 25 CATMATs do catálogo aparece nas bases compiladas
2023–2024 (recorte dominado por medicamentos e reagentes). O módulo fica pronto,
mas desligado em settings.yaml (`complementary.bps.enabled: false`).
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl

from raiox.bronze import write_bronze
from raiox.config import Settings, load_catalog
from raiox.http import HttpClient
from raiox.logs import logger

SOURCE = "bps"


def list_files(client: HttpClient, page_url: str) -> list[str]:
    env = client.request("GET", page_url, key="pagina_bases", expect="text")
    if env is None:
        return []
    links = re.findall(r'href="([^"]+/view)"', env["body"])
    return sorted(
        {link.replace("/view", "/@@download/file") for link in links if "compilad" in link}
    )


def ingest(settings: Settings, client: HttpClient) -> dict[str, Any]:
    cfg = settings.complementary.bps
    codes = {int(i["codigo_catmat"]) for i in load_catalog(settings)}
    files = list_files(client, cfg["page_url"])
    years = [f for f in files if re.search(r"20(2[2-9]|3\d)", f)]
    frames = []
    for url in years:
        name = re.sub(r"[^A-Za-z0-9]+", "_", url.split("/")[-3])[:80] + ".xlsx"
        path = client.download(url, client.store.dir / name)
        if path is None:
            continue
        import fastexcel

        for sheet in fastexcel.read_excel(path).sheet_names:
            df = pl.read_excel(
                path, sheet_name=sheet, engine="calamine", read_options={"header_row": 1}
            )
            if "Código BR" not in df.columns:
                continue
            hit = df.filter(pl.col("Código BR").cast(pl.Int64, strict=False).is_in(list(codes)))
            logger.info(
                "BPS {} aba {}: {} linhas, {} do catálogo", name, sheet, df.height, hit.height
            )
            if hit.height:
                frames.append(hit.with_columns(pl.lit(sheet).alias("aba")))
    if not frames:
        logger.warning("BPS: nenhum item do catálogo nas bases compiladas.")
        return {"linhas_catalogo": 0}
    out = pl.concat(frames, how="diagonal_relaxed")
    write_bronze(settings, "bps_precos", client.snapshot, out, SOURCE, None)
    return {"linhas_catalogo": out.height}
