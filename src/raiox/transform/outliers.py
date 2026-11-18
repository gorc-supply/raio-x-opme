"""Marcação de outliers (seção 8.2): IQR em escala log e MAD (escore-z modificado).

Outliers são MARCADOS, nunca apagados. As estatísticas principais usam a base
sem outliers; o painel permite ver com e sem.
"""

from __future__ import annotations

import polars as pl

MAD_SCALE = 1.4826  # torna o MAD consistente com o desvio-padrão sob normalidade


def flag_outliers(
    df: pl.DataFrame,
    value_col: str,
    group_cols: list[str],
    iqr_k: float,
    mad_z: float,
    min_n: int,
) -> pl.DataFrame:
    """Acrescenta outlier_iqr, outlier_mad e outlier (= iqr OU mad) por grupo.

    Grupos com menos de `min_n` observações não recebem marcação (amostra pequena
    demais para dizer o que é atípico).
    """
    lv = pl.col(value_col).log()
    g = group_cols
    out = df.with_columns(
        lv.alias("_lv"),
        pl.len().over(g).alias("_n"),
    ).with_columns(
        pl.col("_lv").quantile(0.25, interpolation="linear").over(g).alias("_q1"),
        pl.col("_lv").quantile(0.75, interpolation="linear").over(g).alias("_q3"),
        pl.col("_lv").median().over(g).alias("_med"),
    )
    out = out.with_columns(
        (pl.col("_q3") - pl.col("_q1")).alias("_iqr"),
        (pl.col("_lv") - pl.col("_med")).abs().median().over(g).alias("_mad"),
    )
    enough = pl.col("_n") >= min_n
    iqr_flag = (
        (pl.col("_lv") < pl.col("_q1") - iqr_k * pl.col("_iqr"))
        | (pl.col("_lv") > pl.col("_q3") + iqr_k * pl.col("_iqr"))
    ) & enough
    robust_z = (pl.col("_lv") - pl.col("_med")).abs() / (MAD_SCALE * pl.col("_mad"))
    mad_flag = (pl.when(pl.col("_mad") > 0).then(robust_z > mad_z).otherwise(False)) & enough
    out = out.with_columns(
        iqr_flag.fill_null(False).alias("outlier_iqr"),
        mad_flag.fill_null(False).alias("outlier_mad"),
    ).with_columns((pl.col("outlier_iqr") | pl.col("outlier_mad")).alias("outlier"))
    return out.drop("_lv", "_n", "_q1", "_q3", "_med", "_iqr", "_mad")
