"""Bronze → silver: limpeza, tipagem, normalização, deduplicação, LGPD, outliers e deflação."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import polars as pl

from raiox.config import AnalysisCfg, Settings
from raiox.transform.deflate import deflate, ipca_index
from raiox.transform.outliers import flag_outliers
from raiox.transform.units import BASE_PIECE, base_unit_of, normalize_units

DEDUP_KEY = ["idCompra", "idItemCompra", "codigoItemCatalogo"]


# ----------------------------------------------------------------- texto ----
def norm_text(text: str | None) -> str | None:
    """Maiúsculas, sem acento, espaços colapsados. Usado em chaves e agrupamentos."""
    if text is None:
        return None
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    t = re.sub(r"\s+", " ", t.upper()).strip()
    return t or None


def norm_text_expr(col: str) -> pl.Expr:
    return pl.col(col).map_elements(norm_text, return_dtype=pl.String)


# ------------------------------------------------------------------ LGPD ----
MASKED_CPF = re.compile(r"^\*\*\*\.\d{3}\.\d{3}-\*\*$")


def mask_cpf(ni: str | None) -> str | None:
    """Mascara CPF (11 dígitos) no padrão ***.456.789-**; CNPJ fica como está. Idempotente."""
    if ni is None:
        return None
    if MASKED_CPF.match(str(ni)):
        return str(ni)
    digits = re.sub(r"\D", "", str(ni))
    if len(digits) == 11:
        return f"***.{digits[3:6]}.{digits[6:9]}-**"
    return digits or None


def is_cpf(ni: str | None) -> bool:
    if ni is None:
        return False
    return bool(MASKED_CPF.match(str(ni))) or len(re.sub(r"\D", "", str(ni))) == 11


# --------------------------------------------------------------- dedup ----
def deduplicate(df: pl.DataFrame) -> tuple[pl.DataFrame, int]:
    """Mantém a atualização mais recente por idCompra + idItemCompra + codigoItemCatalogo."""
    order_cols = [
        c for c in ("dataHoraAtualizacaoItem", "_fetched_at", "_snapshot") if c in df.columns
    ]
    sorted_df = df.sort(order_cols, descending=True, nulls_last=True) if order_cols else df
    out = sorted_df.unique(subset=DEDUP_KEY, keep="first", maintain_order=True)
    return out, df.height - out.height


# ------------------------------------------------------------- macro ----
def silver_ipca(bronze: pl.DataFrame) -> pl.DataFrame:
    df = (
        bronze.select(
            pl.col("data").cast(pl.Date).alias("mes"),
            pl.col("valor").cast(pl.Float64).alias("variacao_pct"),
            pl.col("_snapshot"),
        )
        .sort("_snapshot")
        .unique(subset=["mes"], keep="last")
        .drop("_snapshot")
        .sort("mes")
    )
    return ipca_index(df)


def silver_cambio(bronze: pl.DataFrame) -> pl.DataFrame:
    return (
        bronze.select(
            pl.col("data").cast(pl.Date).dt.truncate("1mo").alias("mes"),
            pl.col("valor").cast(pl.Float64).alias("usd_brl"),
            pl.col("serie").cast(pl.String).alias("serie_cambio"),
            pl.col("_snapshot"),
        )
        .sort("_snapshot")
        .unique(subset=["mes"], keep="last")
        .drop("_snapshot")
        .sort("mes")
    )


def silver_ufs(bronze: pl.DataFrame) -> pl.DataFrame:
    return (
        bronze.select("codigo_ibge", "uf", "nome", "regiao_sigla", "regiao")
        .unique(subset=["uf"])
        .sort("codigo_ibge")
    )


# ------------------------------------------------------------- comex ----
def silver_comex(bronze: pl.DataFrame, settings: Settings, ufs: pl.DataFrame) -> pl.DataFrame:
    if bronze.height == 0:
        return bronze
    ncm_meta = pl.DataFrame(
        [
            {"ncm": n.ncm, "familia_macro": n.familia, "ncm_historico": n.historico}
            for n in settings.comex.ncms
        ]
    )
    name_to_uf = {norm_text(n): u for n, u in zip(ufs["nome"], ufs["uf"], strict=True)}
    cols = {
        "metricFOB": "fob_usd",
        "metricCIF": "cif_usd",
        "metricFreight": "frete_usd",
        "metricInsurance": "seguro_usd",
        "metricKG": "kg",
        "metricStatistic": "qtd_estatistica",
    }
    df = bronze
    for src in cols:
        if src not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.Float64).alias(src))
    df = (
        df.sort("_snapshot")
        .unique(subset=["coNcm", "year", "monthNumber", "country", "state"], keep="last")
        .select(
            pl.col("coNcm").alias("ncm"),
            pl.col("ncm").alias("descricao_ncm"),
            pl.col("year").cast(pl.Int32).alias("ano"),
            pl.col("monthNumber").cast(pl.Int32).alias("mes_num"),
            pl.date(pl.col("year"), pl.col("monthNumber"), 1).alias("mes"),
            pl.col("country").alias("pais"),
            pl.col("state").alias("uf_nome"),
            *[pl.col(s).cast(pl.Float64).alias(t) for s, t in cols.items()],
        )
        .with_columns(
            pl.col("uf_nome")
            .map_elements(lambda v: name_to_uf.get(norm_text(v)), return_dtype=pl.String)
            .alias("uf")
        )
        .join(ncm_meta, on="ncm", how="left")
        .sort("mes", "ncm", "pais")
    )
    return df


# ----------------------------------------------------------- compras ----
def silver_compras(
    bronze: pl.DataFrame,
    catalog: list[dict[str, Any]],
    ufs: pl.DataFrame,
    index: pl.DataFrame,
    cfg: AnalysisCfg,
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    """Monta compras_precos (silver) e a tabela de descartes com motivo."""
    counts: dict[str, int] = {"bronze": bronze.height}
    cat = pl.DataFrame(
        [
            {
                "codigoItemCatalogo": int(i["codigo_catmat"]),
                "nome_curto": i["nome_curto"],
                "familia": i["familia"],
                "familia_macro": i.get("familia_macro", i["familia"]),
                "ncm_item": str(i.get("ncm") or ""),
                "unidade_base_item": base_unit_of(i.get("unidade_dominante"), cfg) or BASE_PIECE,
            }
            for i in catalog
        ],
        schema={
            "codigoItemCatalogo": pl.Int64,
            "nome_curto": pl.String,
            "familia": pl.String,
            "familia_macro": pl.String,
            "ncm_item": pl.String,
            "unidade_base_item": pl.String,
        },
    )
    df, n_dup = deduplicate(bronze)
    counts["duplicatas"] = n_dup

    df = df.join(cat, on="codigoItemCatalogo", how="left")
    df = normalize_units(df, cfg)
    valid_ufs = set(ufs["uf"].to_list())
    uf = pl.col("estado").cast(pl.String).str.strip_chars().str.to_uppercase()
    df = df.with_columns(
        uf.alias("uf"),
        pl.col("dataCompra")
        .str.slice(0, 10)
        .str.strptime(pl.Date, "%Y-%m-%d", strict=False)
        .alias("data_compra"),
    )
    reason = (
        pl.when(pl.col("nome_curto").is_null())
        .then(pl.lit("fora_do_catalogo"))
        .when(pl.col("precoUnitario").is_null() | (pl.col("precoUnitario") <= 0))
        .then(pl.lit("preco_invalido"))
        .when(pl.col("quantidade").is_null() | (pl.col("quantidade") <= 0))
        .then(pl.lit("quantidade_invalida"))
        .when(pl.col("data_compra").is_null())
        .then(pl.lit("data_ausente"))
        .when(~pl.col("uf").is_in(list(valid_ufs)) | pl.col("uf").is_null())
        .then(pl.lit("uf_invalida"))
        .when(pl.col("motivo_descarte_unidade").is_not_null())
        .then(pl.col("motivo_descarte_unidade"))
        .when(pl.col("unidade_base") != pl.col("unidade_base_item"))
        .then(pl.lit("unidade_incompativel"))
        .otherwise(None)
    )
    df = df.with_columns(reason.alias("motivo_descarte"))

    discards = df.filter(pl.col("motivo_descarte").is_not_null()).select(
        pl.col("idCompra").alias("id_compra"),
        pl.col("idItemCompra").alias("id_item_compra"),
        pl.col("codigoItemCatalogo").alias("codigo_catmat"),
        "uf",
        "data_compra",
        pl.col("siglaUnidadeFornecimento").alias("unidade_fornecimento"),
        pl.col("capacidadeUnidadeFornecimento").alias("capacidade"),
        pl.col("precoUnitario").alias("preco_unitario"),
        "motivo_descarte",
    )
    for motivo, n in discards.group_by("motivo_descarte").len().iter_rows():
        counts[f"descarte_{motivo}"] = n

    ok = df.filter(pl.col("motivo_descarte").is_null())
    ok = ok.with_columns(pl.col("data_compra").dt.truncate("1mo").alias("mes"))
    ok = deflate(ok, "mes", ["preco_unidade_base"], index)
    ok = ok.rename({"preco_unidade_base_real": "preco_real"})
    ok = flag_outliers(
        ok,
        "preco_real",
        ["codigoItemCatalogo", "unidade_base"],
        cfg.outlier_iqr_k,
        cfg.outlier_mad_z,
        cfg.outlier_min_n,
    )
    regions = ufs.select("uf", "regiao")
    ok = ok.join(regions, on="uf", how="left")
    silver = ok.select(
        pl.col("idCompra").alias("id_compra"),
        pl.col("idItemCompra").alias("id_item_compra"),
        pl.col("idCompraItem").alias("id_compra_item"),
        pl.col("codigoItemCatalogo").alias("codigo_catmat"),
        "nome_curto",
        "familia",
        "familia_macro",
        "ncm_item",
        pl.col("descricaoItem").alias("descricao_item"),
        "data_compra",
        "mes",
        pl.col("data_compra").dt.year().alias("ano"),
        "uf",
        "regiao",
        pl.col("codigoMunicipio").alias("codigo_municipio"),
        pl.col("municipio"),
        pl.col("codigoUasg").cast(pl.String).alias("codigo_uasg"),
        pl.col("nomeUasg").alias("nome_uasg"),
        pl.col("codigoOrgao").alias("codigo_orgao"),
        pl.col("nomeOrgao").alias("nome_orgao"),
        pl.col("esfera"),
        pl.col("poder"),
        pl.col("forma"),
        pl.col("modalidade"),
        pl.col("niFornecedor")
        .map_elements(mask_cpf, return_dtype=pl.String)
        .alias("ni_fornecedor"),
        pl.col("niFornecedor").map_elements(is_cpf, return_dtype=pl.Boolean).alias("fornecedor_pf"),
        norm_text_expr("nomeFornecedor").alias("fornecedor"),
        norm_text_expr("marca").alias("marca"),
        pl.col("siglaUnidadeFornecimento").alias("unidade_fornecimento"),
        pl.col("capacidadeUnidadeFornecimento").alias("capacidade"),
        "unidade_base",
        "fator_unidade",
        pl.col("quantidade"),
        "quantidade_base",
        pl.col("precoUnitario").alias("preco_unitario"),
        pl.col("preco_unidade_base").alias("preco_nominal"),
        "preco_real",
        "fator_deflacao",
        "mes_ref_deflacao",
        "outlier_iqr",
        "outlier_mad",
        "outlier",
        pl.col("dataHoraAtualizacaoItem").alias("atualizado_em"),
        pl.col("_snapshot").alias("snapshot"),
    ).sort("codigo_catmat", "data_compra", "id_compra", "id_item_compra")
    # Nome de fornecedor PF: não exibimos nome de pessoa física.
    silver = silver.with_columns(
        pl.when(pl.col("fornecedor_pf"))
        .then(pl.lit("PESSOA FISICA"))
        .otherwise(pl.col("fornecedor"))
        .alias("fornecedor")
    )
    counts["silver"] = silver.height
    counts["outliers"] = int(silver["outlier"].sum())
    return silver, discards, counts
