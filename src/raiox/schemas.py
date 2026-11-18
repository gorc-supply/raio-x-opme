"""Schemas pandera da silver e da gold (seção 7.2).

Falha de schema derruba o pipeline com mensagem clara: melhor falhar do que
publicar número errado.
"""

from __future__ import annotations

import pandera.polars as pa
import polars as pl

from raiox.logs import logger

UF_CODES = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
]  # fmt: skip


class SchemaFailure(RuntimeError):
    pass


def _col(dtype, *checks: pa.Check, **kw) -> pa.Column:
    return pa.Column(dtype, list(checks) or None, coerce=True, **kw)


COMPRAS_SILVER = pa.DataFrameSchema(
    {
        "id_compra": _col(pl.String, nullable=False),
        "id_item_compra": _col(pl.Int64, nullable=False),
        "codigo_catmat": _col(pl.Int64, nullable=False),
        "nome_curto": _col(pl.String, nullable=False),
        "familia": _col(pl.String, nullable=False),
        "data_compra": _col(pl.Date, nullable=False),
        "mes": _col(pl.Date, nullable=False),
        "uf": _col(pl.String, pa.Check.isin(UF_CODES), nullable=False),
        "codigo_uasg": _col(pl.String, nullable=True),
        # LGPD: nenhum CPF completo (11 dígitos) pode chegar à silver.
        "ni_fornecedor": _col(
            pl.String,
            pa.Check(
                lambda d: d.lazyframe.select(
                    ~pl.col(d.key).str.contains(r"^\d{11}$").fill_null(False)
                ),
                name="sem_cpf_completo",
            ),
            nullable=True,
        ),
        "quantidade": _col(pl.Float64, pa.Check.gt(0)),
        "quantidade_base": _col(pl.Float64, pa.Check.gt(0)),
        "preco_unitario": _col(pl.Float64, pa.Check.gt(0)),
        "preco_nominal": _col(pl.Float64, pa.Check.gt(0)),
        "preco_real": _col(pl.Float64, pa.Check.gt(0), nullable=True),
        "unidade_base": _col(pl.String, nullable=False),
        "outlier": _col(pl.Boolean, nullable=False),
    },
    strict=False,
    unique=["id_compra", "id_item_compra", "codigo_catmat"],
    name="silver.compras_precos",
)

IPCA_SILVER = pa.DataFrameSchema(
    {
        "mes": _col(pl.Date, unique=True),
        "variacao_pct": _col(pl.Float64, pa.Check.in_range(-5, 10)),
        "indice": _col(pl.Float64, pa.Check.gt(0)),
    },
    name="silver.ipca",
)

CAMBIO_SILVER = pa.DataFrameSchema(
    {"mes": _col(pl.Date, unique=True), "usd_brl": _col(pl.Float64, pa.Check.in_range(0.5, 20))},
    strict=False,
    name="silver.cambio",
)

COMEX_SILVER = pa.DataFrameSchema(
    {
        "ncm": _col(pl.String, pa.Check.str_matches(r"^\d{8}$")),
        "ano": _col(pl.Int32),
        "mes": _col(pl.Date),
        "pais": _col(pl.String, nullable=True),
        "fob_usd": _col(pl.Float64, pa.Check.ge(0), nullable=True),
        "kg": _col(pl.Float64, pa.Check.ge(0), nullable=True),
    },
    strict=False,
    name="silver.comex",
)

UFS_SILVER = pa.DataFrameSchema(
    {"uf": _col(pl.String, pa.Check.isin(UF_CODES), unique=True), "regiao": _col(pl.String)},
    strict=False,
    name="silver.ufs",
)

# ------------------------------------------------------------------ gold ----
PRECO_ITEM_UF = pa.DataFrameSchema(
    {
        "codigo_catmat": _col(pl.Int64),
        "uf": _col(pl.String, pa.Check.isin([*UF_CODES, "BR"])),
        "base": _col(pl.String, pa.Check.isin(["sem_outliers", "com_outliers"])),
        "n_registros": _col(pl.Int64, pa.Check.ge(1)),
        "n_compras": _col(pl.Int64, pa.Check.ge(1)),
        "n_orgaos": _col(pl.Int64, pa.Check.ge(1)),
        "mediana": _col(pl.Float64, pa.Check.gt(0)),
        "p10": _col(pl.Float64, pa.Check.gt(0)),
        "p90": _col(pl.Float64, pa.Check.gt(0)),
        "amostra_suficiente": _col(pl.Boolean),
    },
    strict=False,
    checks=[
        pa.Check(
            lambda d: d.lazyframe.select((pl.col("p10") <= pl.col("p90")).all()).collect().item(),
            name="p10<=p90",
        )
    ],
    unique=["codigo_catmat", "uf", "base"],
    name="gold.preco_item_uf",
)

DISPERSAO_ITEM = pa.DataFrameSchema(
    {
        "codigo_catmat": _col(pl.Int64, unique=True),
        "n_ufs_elegiveis": _col(pl.Int64, pa.Check.ge(0)),
        "razao": _col(pl.Float64, pa.Check.ge(1), nullable=True),
        "ic_inf": _col(pl.Float64, nullable=True),
        "ic_sup": _col(pl.Float64, nullable=True),
        "robustez": _col(
            pl.String, pa.Check.isin(["forte", "moderado", "fraco", "sem_comparacao"])
        ),
    },
    strict=False,
    name="gold.dispersao_item",
)

SERIE_ITEM_MES = pa.DataFrameSchema(
    {
        "codigo_catmat": _col(pl.Int64),
        "mes": _col(pl.Date),
        "n_registros": _col(pl.Int64, pa.Check.ge(1)),
        "mediana_nominal": _col(pl.Float64, pa.Check.gt(0)),
        "mediana_real": _col(pl.Float64, pa.Check.gt(0), nullable=True),
    },
    strict=False,
    unique=["codigo_catmat", "mes"],
    name="gold.serie_item_mes",
)

FORNECEDORES_ITEM = pa.DataFrameSchema(
    {
        "codigo_catmat": _col(pl.Int64),
        "tipo": _col(pl.String, pa.Check.isin(["fornecedor", "marca"])),
        "nome": _col(pl.String),
        "participacao_valor": _col(pl.Float64, pa.Check.in_range(0, 1)),
        "hhi": _col(pl.Float64, pa.Check.in_range(0, 10000)),
    },
    strict=False,
    name="gold.fornecedores_item",
)

IMPORTACAO_NCM_ANO = pa.DataFrameSchema(
    {
        "ncm": _col(pl.String, pa.Check.str_matches(r"^\d{8}$")),
        "ano": _col(pl.Int32),
        "fob_usd": _col(pl.Float64, pa.Check.ge(0)),
        "hhi_origem": _col(pl.Float64, pa.Check.in_range(0, 10000), nullable=True),
        "unidade_estatistica": _col(pl.String, pa.Check.isin(["UN", "KG"])),
    },
    strict=False,
    unique=["ncm", "ano"],
    name="gold.importacao_ncm_ano",
)

PONTE = pa.DataFrameSchema(
    {
        "familia_macro": _col(pl.String, unique=True),
        "comparavel_por_unidade": _col(pl.Boolean),
        "componentes_diferenca": _col(pl.String),
    },
    strict=False,
    name="gold.ponte_preco_importacao",
)

ACHADOS = pa.DataFrameSchema(
    {
        "id": _col(pl.String, unique=True),
        "tipo": _col(pl.String),
        "frase": _col(pl.String, pa.Check.str_length(min_value=20)),
        "periodo": _col(pl.String),
        "fonte": _col(pl.String),
        "robustez": _col(pl.String, pa.Check.isin(["forte", "moderado", "fraco"])),
        "n": _col(pl.Int64, pa.Check.ge(0)),
    },
    strict=False,
    name="gold.achados",
)

QUALIDADE = pa.DataFrameSchema(
    {"secao": _col(pl.String), "chave": _col(pl.String), "valor": _col(pl.Float64, nullable=True)},
    strict=False,
    name="gold.qualidade",
)

FORBIDDEN_WORDS = ("superfatur", "fraude", "roubo", "desvio de dinheiro", "propina", "corrup")


def validate(df: pl.DataFrame, schema: pa.DataFrameSchema) -> pl.DataFrame:
    try:
        out = schema.validate(df, lazy=True)
    except (pa.errors.SchemaErrors, pa.errors.SchemaError) as exc:
        msg = f"Falha de schema em {schema.name}: {str(exc)[:2000]}"
        logger.error(msg)
        raise SchemaFailure(msg) from exc
    logger.debug("Schema {} ok ({} linhas)", schema.name, df.height)
    return out


def check_language(texts: list[str]) -> None:
    """Guardrail da seção 9: nenhum texto gerado pode conter termos acusatórios."""
    for t in texts:
        low = (t or "").lower()
        for w in FORBIDDEN_WORDS:
            if w in low:
                raise SchemaFailure(f"Texto viola a seção 9 (termo '{w}'): {t[:200]}")
