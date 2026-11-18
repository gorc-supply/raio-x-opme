"""Deflação pelo IPCA (série 433) para reais constantes do último mês disponível (seção 8.5)."""

from __future__ import annotations

import polars as pl


def ipca_index(ipca: pl.DataFrame) -> pl.DataFrame:
    """Converte variação % mensal em número-índice (primeiro mês = 1,0).

    Entrada: colunas `mes` (Date, primeiro dia do mês) e `variacao_pct`.
    Saída: `mes`, `variacao_pct`, `indice`.
    """
    s = ipca.sort("mes")
    return s.with_columns(
        (1 + pl.col("variacao_pct") / 100).cum_prod().alias("indice"),
    )


def reference_month(index: pl.DataFrame) -> pl.Date:
    return index["mes"].max()


def deflate(
    df: pl.DataFrame,
    month_col: str,
    value_cols: list[str],
    index: pl.DataFrame,
    suffix: str = "_real",
) -> pl.DataFrame:
    """Leva valores nominais para R$ do último mês do índice.

    valor_real = valor_nominal × (índice_ref / índice_mês). Meses posteriores ao
    último IPCA disponível recebem fator 1 (não há inflação conhecida a corrigir);
    meses anteriores ao início do índice ficam nulos (não deflacionáveis).
    """
    ref = index.sort("mes").tail(1)
    ref_month = ref["mes"][0]
    ref_idx = ref["indice"][0]
    first_month = index["mes"].min()
    joined = df.join(
        index.select(pl.col("mes").alias(month_col), pl.col("indice").alias("_idx")),
        on=month_col,
        how="left",
    )
    factor = (
        pl.when(pl.col(month_col) > ref_month)
        .then(pl.lit(1.0))
        .when(pl.col(month_col) < first_month)
        .then(None)
        .otherwise(ref_idx / pl.col("_idx"))
    )
    joined = joined.with_columns(factor.alias("fator_deflacao"))
    joined = joined.with_columns(
        [(pl.col(c) * pl.col("fator_deflacao")).alias(f"{c}{suffix}") for c in value_cols]
    )
    return joined.drop("_idx").with_columns(pl.lit(ref_month).alias("mes_ref_deflacao"))
