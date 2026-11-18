"""Ponte Tabela SUS (SIGTAP) × preço praticado nas compras públicas.

O SIGTAP é o valor que o SUS REEMBOLSA ao prestador por unidade de OPME; não é preço de
compra. A razão "mediana paga ÷ valor de tabela" mede a defasagem da tabela, não a conduta
de quem compra. O mapa entre códigos SIGTAP e itens CATMAT é curado à mão
(config/mapa_sigtap_catmat.yaml) e tem nível de confiança por par.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import yaml

from raiox.analytics.dispersion import Period, _cluster_bootstrap_median
from raiox.config import Settings
from raiox.logs import logger

CONFIDENCE_LEVELS = ("alta", "media", "baixa")
PAIR_COLUMNS = {
    "codigo_sigtap": pl.String,
    "descricao_sigtap": pl.String,
    "codigo_catmat": pl.Int64,
    "familia": pl.String,
    "confianca": pl.String,
    "justificativa": pl.String,
}


@dataclass(frozen=True)
class Mapping:
    validated: bool
    pairs: pl.DataFrame


def parse_mapping(data: dict) -> Mapping:
    pairs = data.get("pares") or []
    for p in pairs:
        missing = [k for k in PAIR_COLUMNS if p.get(k) in (None, "")]
        if missing:
            raise ValueError(f"Par SIGTAP×CATMAT incompleto ({missing}): {p}")
        if p["confianca"] not in CONFIDENCE_LEVELS:
            raise ValueError(f"confianca inválida: {p['confianca']!r} (use {CONFIDENCE_LEVELS})")
        if not str(p["codigo_sigtap"]).isdigit() or len(str(p["codigo_sigtap"])) != 10:
            raise ValueError(f"codigo_sigtap deve ter 10 dígitos: {p['codigo_sigtap']!r}")
    df = pl.DataFrame(
        [{k: p[k] for k in PAIR_COLUMNS} for p in pairs], schema=PAIR_COLUMNS, orient="row"
    )
    dup = df.filter(pl.struct("codigo_sigtap", "codigo_catmat").is_duplicated())
    if dup.height:
        raise ValueError(f"Pares duplicados no mapa SIGTAP×CATMAT: {dup.rows()}")
    return Mapping(bool(data.get("validado_por_gabriel", False)), df)


def load_mapping(settings: Settings) -> Mapping | None:
    rel = settings.complementary.sigtap.get("mapa", "config/mapa_sigtap_catmat.yaml")
    path = settings.root / Path(rel)
    if not path.exists():
        return None
    return parse_mapping(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def format_code(code: str) -> str:
    """0702040614 → 07.02.04.061-4 (máscara usada na consulta web do SIGTAP)."""
    c = str(code)
    return f"{c[0:2]}.{c[2:4]}.{c[4:6]}.{c[6:9]}-{c[9]}" if len(c) == 10 else c


def _value_at(sv: pl.DataFrame, code: str, month: date, how: str) -> dict | None:
    """Competência vigente em `month`: a última ≤ month (how='le'); se não houver, a primeira."""
    g = sv.filter(pl.col("codigo_sigtap") == code).sort("mes_competencia")
    if g.height == 0:
        return None
    le = g.filter(pl.col("mes_competencia") <= month)
    if how == "le" and le.height:
        return le.row(-1, named=True)
    return g.row(-1 if how == "last" else 0, named=True)


def ponte_sigtap_preco(
    sigtap: pl.DataFrame,
    comp: pl.DataFrame,
    period: Period,
    mapping: Mapping,
    reps: int,
    seed: int,
    ci_level: float,
) -> pl.DataFrame:
    """Uma linha por par do mapa: valor SIGTAP (nominal e real) × mediana praticada no período."""
    rng = np.random.default_rng(seed + 7)
    alpha = (1 - ci_level) / 2
    base = period.filter(comp.filter(~pl.col("outlier") & pl.col("preco_real").is_not_null()))
    names = comp.select("codigo_catmat", "nome_curto").unique(subset="codigo_catmat")
    rows = []
    for p in mapping.pairs.iter_rows(named=True):
        cur = _value_at(sigtap, p["codigo_sigtap"], date.max, "last")
        if cur is None:
            logger.warning("SIGTAP {} do mapa não existe na base baixada", p["codigo_sigtap"])
            continue
        start = _value_at(sigtap, p["codigo_sigtap"], period.start, "le")
        first = _value_at(sigtap, p["codigo_sigtap"], date.min, "first")
        hist = sigtap.filter(pl.col("codigo_sigtap") == p["codigo_sigtap"])["valor_opme"]
        g = base.filter(pl.col("codigo_catmat") == p["codigo_catmat"])
        n = g["id_compra"].n_unique()
        med = float(g["preco_real"].median()) if n else None
        ratio = lo = hi = None
        if n and cur["valor_opme_real"]:
            ratio = med / cur["valor_opme_real"]
            boots = _cluster_bootstrap_median(
                g["preco_real"].to_numpy(), g["id_compra"].to_numpy(), reps, rng
            )
            lo, hi = (
                float(x) for x in np.quantile(boots / cur["valor_opme_real"], [alpha, 1 - alpha])
            )
        nm = names.filter(pl.col("codigo_catmat") == p["codigo_catmat"])
        rows.append(
            {
                "codigo_sigtap": p["codigo_sigtap"],
                "codigo_sigtap_fmt": format_code(p["codigo_sigtap"]),
                "descricao_sigtap": cur["descricao_sigtap"],
                "codigo_catmat": p["codigo_catmat"],
                "nome_curto": nm["nome_curto"][0] if nm.height else None,
                "familia": p["familia"],
                "confianca": p["confianca"],
                "justificativa": p["justificativa"],
                "mapa_validado": mapping.validated,
                "competencia_sigtap": cur["competencia"],
                "valor_sigtap_nominal": cur["valor_opme"],
                "valor_sigtap_real": cur["valor_opme_real"],
                "competencia_inicio_periodo": start["competencia"] if start else None,
                "valor_sigtap_inicio_periodo": start["valor_opme"] if start else None,
                "sigtap_mudou_no_periodo": bool(start and start["valor_opme"] != cur["valor_opme"]),
                "competencia_mais_antiga": first["competencia"],
                "valor_sigtap_mais_antigo_nominal": first["valor_opme"],
                "valor_sigtap_mais_antigo_real": first["valor_opme_real"],
                "valor_sigtap_min_nominal": float(hist.min()),
                "valor_sigtap_max_nominal": float(hist.max()),
                "n_competencias": hist.len(),
                "sigtap_valor_constante": hist.n_unique() == 1,
                "mediana_preco_real": med,
                "p10_preco_real": float(g["preco_real"].quantile(0.1, "linear")) if n else None,
                "p90_preco_real": float(g["preco_real"].quantile(0.9, "linear")) if n else None,
                "n_compras": n,
                "n_orgaos": g["codigo_uasg"].n_unique() if n else 0,
                "razao_preco_sigtap": ratio,
                "ic_inf": lo,
                "ic_sup": hi,
                "periodo_inicio": period.start,
                "periodo_fim": period.end,
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).with_columns(
        pl.col("codigo_catmat").cast(pl.Int64), pl.col("n_compras").cast(pl.Int64)
    )


def sigtap_serie(sigtap: pl.DataFrame, mapping: Mapping) -> pl.DataFrame:
    """Evolução do valor de tabela (nominal e real) dos códigos SIGTAP presentes no mapa."""
    codes = mapping.pairs.select("codigo_sigtap").unique()
    return (
        sigtap.join(codes, on="codigo_sigtap", how="semi")
        .select(
            "codigo_sigtap",
            "descricao_sigtap",
            "competencia",
            "mes_competencia",
            pl.col("valor_opme").alias("valor_nominal"),
            pl.col("valor_opme_real").alias("valor_real"),
            "mes_ref_deflacao",
        )
        .sort(["codigo_sigtap", "competencia"])
    )
