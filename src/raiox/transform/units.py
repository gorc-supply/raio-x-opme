"""Normalização de unidade de fornecimento (seção 8.1).

Regra: só se compara o mesmo CATMAT na mesma unidade-base. Quando a unidade
é uma embalagem com N unidades, o preço é dividido por N. Quando não dá para
normalizar com segurança, a linha é descartada e o motivo é contado.
"""

from __future__ import annotations

import polars as pl

from raiox.config import AnalysisCfg

BASE_PIECE = "UN"
BASE_SET = "CONJUNTO"


def _clean(col: str) -> pl.Expr:
    return (
        pl.col(col)
        .cast(pl.String)
        .str.to_uppercase()
        .str.strip_chars()
        .str.replace_all(r"\.", "")
        .replace("", None)
    )


def base_unit_of(sigla: str | None, cfg: AnalysisCfg) -> str | None:
    """Unidade-base de uma sigla de fornecimento isolada (usada para o catálogo)."""
    if not sigla:
        return None
    s = sigla.strip().upper().replace(".", "")
    if s in cfg.unit_aliases_piece:
        return BASE_PIECE
    if s in cfg.unit_aliases_set:
        return BASE_SET
    if s in cfg.unit_aliases_pack:
        return BASE_PIECE
    return s


def normalize_units(df: pl.DataFrame, cfg: AnalysisCfg) -> pl.DataFrame:
    """Acrescenta unidade_base, fator_unidade, preco_unidade_base, quantidade_base
    e motivo_descarte_unidade (nulo quando a linha é aproveitável)."""
    piece = cfg.unit_aliases_piece
    pack = cfg.unit_aliases_pack
    sets = cfg.unit_aliases_set
    sigla = pl.coalesce(_clean("siglaUnidadeFornecimento"), _clean("nomeUnidadeFornecimento"))
    medida = _clean("siglaUnidadeMedida")
    cap = pl.col("capacidadeUnidadeFornecimento").cast(pl.Float64)

    out = df.with_columns(sigla.alias("_sigla"), medida.alias("_medida"), cap.alias("_cap"))
    s = pl.col("_sigla")
    m = pl.col("_medida")
    c = pl.col("_cap")
    trivial = c.is_null() | (c == 0) | (c == 1)
    out = out.with_columns(
        pl.when(s.is_null())
        .then(pl.lit("unidade_ausente"))
        .when(s.is_in(piece) & ~trivial)
        .then(pl.lit("capacidade_ambigua"))
        .when(s.is_in(sets) & ~trivial)
        .then(pl.lit("capacidade_ambigua"))
        .when(s.is_in(pack) & ~(c > 0))
        .then(pl.lit("embalagem_sem_capacidade"))
        .when(s.is_in(pack) & ~m.is_in(piece))
        .then(pl.lit("embalagem_sem_unidade_medida"))
        .when(~(s.is_in(piece) | s.is_in(pack) | s.is_in(sets)))
        .then(pl.lit("unidade_desconhecida"))
        .otherwise(None)
        .alias("motivo_descarte_unidade"),
        pl.when(s.is_in(piece) | s.is_in(pack))
        .then(pl.lit(BASE_PIECE))
        .when(s.is_in(sets))
        .then(pl.lit(BASE_SET))
        .otherwise(s)
        .alias("unidade_base"),
        pl.when(s.is_in(pack) & (c > 0)).then(c).otherwise(pl.lit(1.0)).alias("fator_unidade"),
    )
    out = out.with_columns(
        (pl.col("precoUnitario") / pl.col("fator_unidade")).alias("preco_unidade_base"),
        (pl.col("quantidade") * pl.col("fator_unidade")).alias("quantidade_base"),
    ).drop("_sigla", "_medida", "_cap")
    return out
