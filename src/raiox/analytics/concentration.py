"""Concentração (seção 8.9): HHI e participação dos maiores (CR-n)."""

from __future__ import annotations

import polars as pl

from raiox.analytics.dispersion import ITEM_COLS, Period


def hhi(shares: list[float] | pl.Series) -> float:
    """Índice Herfindahl-Hirschman em pontos (0–10.000), com participações em fração."""
    s = pl.Series(shares, dtype=pl.Float64)
    return float(((s * 100) ** 2).sum())


def cr(shares: list[float] | pl.Series, n: int) -> float:
    s = pl.Series(shares, dtype=pl.Float64).sort(descending=True)
    return float(s.head(n).sum())


def fornecedores_item(silver: pl.DataFrame, period: Period, top_n: int) -> pl.DataFrame:
    """Participação por fornecedor e por marca (valor em R$ reais), HHI e CR-n por item."""
    df = period.filter(silver).filter(pl.col("preco_real").is_not_null())
    df = df.with_columns((pl.col("preco_real") * pl.col("quantidade_base")).alias("valor_real"))
    frames = []
    for tipo, col in (("fornecedor", "fornecedor"), ("marca", "marca")):
        agg = (
            df.with_columns(pl.col(col).fill_null("NÃO INFORMADO").alias("nome"))
            .group_by([*ITEM_COLS, "nome"])
            .agg(
                pl.col("id_compra").n_unique().cast(pl.Int64).alias("n_compras"),
                pl.len().cast(pl.Int64).alias("n_registros"),
                pl.col("quantidade_base").sum().alias("quantidade"),
                pl.col("valor_real").sum().alias("valor_real"),
            )
            .with_columns(
                (pl.col("valor_real") / pl.col("valor_real").sum().over("codigo_catmat")).alias(
                    "participacao_valor"
                ),
                (pl.col("n_registros") / pl.col("n_registros").sum().over("codigo_catmat")).alias(
                    "participacao_registros"
                ),
            )
            .with_columns(
                (((pl.col("participacao_valor") * 100) ** 2).sum().over("codigo_catmat")).alias(
                    "hhi"
                ),
                pl.col("participacao_valor")
                .rank("ordinal", descending=True)
                .over("codigo_catmat")
                .cast(pl.Int64)
                .alias("rank"),
                pl.lit(tipo).alias("tipo"),
            )
        )
        crn = (
            agg.filter(pl.col("rank") <= top_n)
            .group_by("codigo_catmat")
            .agg(pl.col("participacao_valor").sum().alias(f"cr{top_n}"))
        )
        frames.append(agg.join(crn, on="codigo_catmat", how="left"))
    out = pl.concat(frames, how="diagonal_relaxed").with_columns(
        pl.lit(period.start).alias("periodo_inicio"), pl.lit(period.end).alias("periodo_fim")
    )
    return out.sort("codigo_catmat", "tipo", "rank")
