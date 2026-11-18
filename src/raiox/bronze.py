"""Utilitários da camada bronze: parquet fiel à fonte + colunas de linhagem."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from raiox.config import Settings
from raiox.logs import logger


def frame_from_records(
    records: list[dict[str, Any]],
    schema: dict[str, pl.DataType],
) -> pl.DataFrame:
    """Monta um DataFrame com tipos explícitos para as colunas conhecidas.

    Colunas novas (não previstas) entram como texto, para não perder informação.
    """
    if not records:
        return pl.DataFrame(schema=schema)
    extra = sorted({k for r in records for k in r} - set(schema))
    full_schema: dict[str, pl.DataType] = {**schema, **{k: pl.String for k in extra}}
    cols: dict[str, list[Any]] = {k: [] for k in full_schema}
    for r in records:
        for k in full_schema:
            cols[k].append(r.get(k))
    series = []
    for k, dtype in full_schema.items():
        values = cols[k]
        if dtype == pl.String:
            values = [None if v is None else str(v) for v in values]
            series.append(pl.Series(k, values, dtype=pl.String))
        else:
            s = pl.Series(k, [None if v in ("", None) else v for v in values], strict=False)
            series.append(s.cast(dtype, strict=False))
    return pl.DataFrame(series)


def write_bronze(
    settings: Settings,
    table: str,
    snapshot: str,
    df: pl.DataFrame,
    source: str,
    fetched_at: str | None,
) -> Path:
    df = df.with_columns(
        pl.lit(source).alias("_source"),
        pl.lit(fetched_at).alias("_fetched_at"),
        pl.lit(snapshot).alias("_snapshot"),
    )
    out = settings.path("bronze") / table / f"{snapshot}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out)
    logger.info("Bronze {} [{}]: {} linhas → {}", table, snapshot, df.height, out.name)
    return out


def read_bronze(settings: Settings, table: str) -> pl.DataFrame:
    """Lê todos os snapshots de uma tabela bronze (histórico acumulado, append-only)."""
    base = settings.path("bronze") / table
    files = sorted(base.glob("*.parquet")) if base.exists() else []
    if not files:
        return pl.DataFrame()
    frames = [pl.read_parquet(f) for f in files]
    return pl.concat(frames, how="diagonal_relaxed")
