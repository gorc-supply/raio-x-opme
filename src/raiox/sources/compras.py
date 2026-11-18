"""Compras.gov.br — API de Dados Abertos (pesquisa de preços praticados).

Endpoint confirmado na Fase 1 (ver docs/FONTES.md):
GET /modulo-pesquisa-preco/1_consultarMaterial?tipo=codigoItemCatalogo&codigo=<CATMAT>
(o parâmetro `codigoItemCatalogo` documentado em versões antigas do manual não existe mais).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import polars as pl

from raiox.bronze import frame_from_records, write_bronze
from raiox.config import Settings
from raiox.http import HttpClient, check_contract
from raiox.logs import logger
from raiox.state import read_state, write_state

SOURCE = "compras"

PRICE_SCHEMA: dict[str, pl.DataType] = {
    "idCompra": pl.String,
    "idItemCompra": pl.Int64,
    "numeroItemCompra": pl.Int64,
    "idCompraItem": pl.String,
    "forma": pl.String,
    "modalidade": pl.Int64,
    "criterioJulgamento": pl.String,
    "dataCompra": pl.String,
    "dataResultado": pl.String,
    "dataHoraAtualizacaoCompra": pl.String,
    "dataHoraAtualizacaoItem": pl.String,
    "dataHoraAtualizacaoUasg": pl.String,
    "dataAtualizacaoFato": pl.String,
    "codigoItemCatalogo": pl.Int64,
    "descricaoItem": pl.String,
    "descricaoDetalhadaItem": pl.String,
    "objetoCompra": pl.String,
    "codigoPdm": pl.String,
    "nomePdm": pl.String,
    "codigoClasse": pl.Int64,
    "nomeClasse": pl.String,
    "siglaUnidadeFornecimento": pl.String,
    "nomeUnidadeFornecimento": pl.String,
    "capacidadeUnidadeFornecimento": pl.Float64,
    "siglaUnidadeMedida": pl.String,
    "nomeUnidadeMedida": pl.String,
    "quantidade": pl.Float64,
    "precoUnitario": pl.Float64,
    "percentualMaiorDesconto": pl.Float64,
    "niFornecedor": pl.String,
    "nomeFornecedor": pl.String,
    "marca": pl.String,
    "codigoUasg": pl.String,
    "nomeUasg": pl.String,
    "codigoOrgao": pl.Int64,
    "nomeOrgao": pl.String,
    "estado": pl.String,
    "codigoMunicipio": pl.Int64,
    "municipio": pl.String,
    "poder": pl.String,
    "esfera": pl.String,
}
EXPECTED_PRICE_FIELDS = set(PRICE_SCHEMA)
CRITICAL_PRICE_FIELDS = {
    "idCompra",
    "idItemCompra",
    "codigoItemCatalogo",
    "precoUnitario",
    "quantidade",
    "estado",
    "dataCompra",
    "siglaUnidadeFornecimento",
    "capacidadeUnidadeFornecimento",
    "codigoUasg",
}

CATALOG_SCHEMA: dict[str, pl.DataType] = {
    "codigoItem": pl.Int64,
    "codigoGrupo": pl.Int64,
    "nomeGrupo": pl.String,
    "codigoClasse": pl.Int64,
    "nomeClasse": pl.String,
    "codigoPdm": pl.Int64,
    "nomePdm": pl.String,
    "descricaoItem": pl.String,
    "statusItem": pl.Boolean,
    "itemSustentavel": pl.Boolean,
    "codigo_ncm": pl.String,
    "descricao_ncm": pl.String,
    "aplica_margem_preferencia": pl.Boolean,
    "dataHoraAtualizacao": pl.String,
}


def mask_pf_suppliers(df: pl.DataFrame) -> pl.DataFrame:
    """LGPD: esta bronze é versionada (histórico append-only), então CPF de fornecedor
    pessoa física é mascarado já aqui, e o nome é substituído. Única alteração em relação à fonte."""
    from raiox.transform.normalize import is_cpf, mask_cpf

    if df.height == 0 or "niFornecedor" not in df.columns:
        return df
    pf = pl.col("niFornecedor").map_elements(is_cpf, return_dtype=pl.Boolean).fill_null(False)
    return df.with_columns(
        pl.col("niFornecedor").map_elements(mask_cpf, return_dtype=pl.String),
        pl.when(pf)
        .then(pl.lit("PESSOA FISICA"))
        .otherwise(pl.col("nomeFornecedor"))
        .alias("nomeFornecedor"),
    )


class ComprasSource:
    def __init__(self, settings: Settings, client: HttpClient):
        self.s = settings
        self.c = client
        self.cfg = settings.compras

    def url(self, path: str) -> str:
        return self.cfg.base_url.rstrip("/") + path

    # -- grafia do módulo de pesquisa de preço --------------------------------
    def price_path(self, probe_code: int | str) -> str:
        """Descobre (e memoriza em data/state) qual grafia do módulo responde."""
        st = read_state(self.s, "compras_price_path")
        if st and st.get("path") in self.cfg.price_path_candidates:
            return st["path"]
        if self.s.offline:
            return self.cfg.price_path_candidates[0]
        for path in self.cfg.price_path_candidates:
            env = self.c.request(
                "GET",
                self.url(path),
                key=f"probe_path_{path.strip('/').split('/')[0]}",
                params={
                    "pagina": 1,
                    "tamanhoPagina": 10,
                    "tipo": "codigoItemCatalogo",
                    "codigo": str(probe_code),
                },
            )
            if env is not None and isinstance(env["body"], dict) and "resultado" in env["body"]:
                write_state(self.s, "compras_price_path", {"path": path})
                logger.info("Módulo de pesquisa de preço: grafia que funciona = {}", path)
                return path
            logger.warning("Grafia {} não respondeu; tentando a próxima", path)
        logger.error("Nenhuma grafia do módulo de pesquisa de preço respondeu; usando a primeira")
        return self.cfg.price_path_candidates[0]

    # -- preços ----------------------------------------------------------------
    def iter_prices(
        self,
        codigo: int | str,
        tipo: str = "codigoItemCatalogo",
        extra: dict[str, Any] | None = None,
        key_prefix: str | None = None,
    ) -> Iterator[dict[str, Any]]:
        path = self.price_path(codigo)
        params = {"tipo": tipo, "codigo": str(codigo), **(extra or {})}
        prefix = key_prefix or f"preco_{'item' if tipo == 'codigoItemCatalogo' else 'pdm'}_{codigo}"
        for env in self.c.paginate(self.url(path), params, prefix, self.cfg.page_size):
            rows = env["body"].get("resultado", [])
            if rows:
                check_contract(
                    "compras.1_consultarMaterial",
                    rows[0],
                    EXPECTED_PRICE_FIELDS,
                    CRITICAL_PRICE_FIELDS,
                )
            yield from rows

    def count_prices(self, codigo: int | str, tipo: str = "codigoItemCatalogo") -> int | None:
        """Total de registros de preço de um item (chamada barata, tamanhoPagina=10)."""
        path = self.price_path(codigo)
        env = self.c.get_json(
            self.url(path),
            key=f"count_{tipo}_{codigo}",
            params={"pagina": 1, "tamanhoPagina": 10, "tipo": tipo, "codigo": str(codigo)},
        )
        if env is None:
            return None
        return int(env["body"].get("totalRegistros", 0))

    def ingest_items(self, codes: list[int]) -> dict[int, int]:
        counts: dict[int, int] = {}
        for i, code in enumerate(codes, 1):
            n = sum(1 for _ in self.iter_prices(code))
            counts[code] = n
            logger.info("Compras [{}/{}] CATMAT {}: {} registros", i, len(codes), code, n)
        return counts

    # -- catálogo ----------------------------------------------------------------
    def iter_catalog(self, key_prefix: str, **filters: Any) -> Iterator[dict[str, Any]]:
        for env in self.c.paginate(
            self.url(self.cfg.catalog_item_path), filters, key_prefix, self.cfg.page_size
        ):
            yield from env["body"].get("resultado", [])

    def iter_pdms(self, group: int) -> Iterator[dict[str, Any]]:
        for env in self.c.paginate(
            self.url(self.cfg.catalog_pdm_path),
            {"codigoGrupo": group},
            f"pdm_grupo_{group}",
            self.cfg.page_size,
        ):
            yield from env["body"].get("resultado", [])

    def detail(self, codigo_item: int, data_inicio: str, data_fim: str) -> list[dict[str, Any]]:
        """Detalhe (descricaoDetalhadaItem) — só para auditoria de amostras."""
        env = self.c.get_json(
            self.url(self.cfg.detail_path),
            key=f"detalhe_{codigo_item}_{data_inicio}_{data_fim}",
            params={
                "pagina": 1,
                "tamanhoPagina": 10,
                "codigoItemCatalogo": codigo_item,
                "dataCompraInicio": data_inicio,
                "dataCompraFim": data_fim,
            },
        )
        return [] if env is None else env["body"].get("resultado", [])


def build_bronze(settings: Settings, client: HttpClient) -> int:
    """Raw do snapshot → bronze/compras_precos/<snapshot>.parquet."""
    records: list[dict[str, Any]] = []
    fetched = None
    seen_keys: set[str] = set()
    for key, env in client.store.iter_envelopes("preco_item_"):
        seen_keys.add(key)
        fetched = max(fetched or "", env["meta"]["fetched_at"])
        records.extend(env["body"].get("resultado", []))
    if not records:
        logger.warning("Compras: nenhum registro no raw do snapshot {}", client.snapshot)
        return 0
    df = mask_pf_suppliers(frame_from_records(records, PRICE_SCHEMA))
    write_bronze(settings, "compras_precos", client.snapshot, df, SOURCE, fetched)

    cat_records: list[dict[str, Any]] = []
    for _, env in client.store.iter_envelopes("catalogo_item_"):
        cat_records.extend(env["body"].get("resultado", []))
    if cat_records:
        cat = (
            frame_from_records(cat_records, CATALOG_SCHEMA)
            .unique(subset=["codigoItem"], maintain_order=True)
            .sort("codigoItem")
        )
        write_bronze(settings, "catmat_itens", client.snapshot, cat, SOURCE, fetched)
    return df.height


def ingest(settings: Settings, client: HttpClient, items: list[dict[str, Any]]) -> dict[str, int]:
    src = ComprasSource(settings, client)
    codes = [int(it["codigo_catmat"]) for it in items]
    counts = src.ingest_items(codes)
    # Ficha CATMAT de cada item (descrição oficial, NCM, status).
    for code in codes:
        for _ in src.iter_catalog(f"catalogo_item_{code}", codigoItem=code):
            pass
    n = build_bronze(settings, client)
    return {
        "itens": len(codes),
        "registros": n,
        "itens_sem_dados": sum(1 for v in counts.values() if v == 0),
    }
