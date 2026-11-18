"""Preço por item × UF, dispersão entre UFs (com IC bootstrap) e série temporal real.

Regras da seção 8: mediana como medida central; UF só entra em comparação com
amostra mínima (compras distintas e órgãos distintos); razão maior/menor mediana
com IC bootstrap de semente fixa; "achado" só com IC inferior acima do limite e
sem UF cuja mediana seja determinada por um único órgão comprador.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import polars as pl

from raiox.config import AnalysisCfg

ITEM_COLS = ["codigo_catmat", "nome_curto", "familia", "familia_macro", "unidade_base"]


# ---------------------------------------------------------------- período ----
@dataclass(frozen=True)
class Period:
    start: date
    end: date

    @property
    def label(self) -> str:
        return f"{self.start:%m/%Y} a {self.end:%m/%Y}"

    def filter(self, df: pl.DataFrame, col: str = "mes") -> pl.DataFrame:
        return df.filter(pl.col(col).is_between(self.start, self.end))


def _add_months(d: date, months: int) -> date:
    y, m = d.year, d.month + months
    while m <= 0:
        m += 12
        y -= 1
    while m > 12:
        m -= 12
        y += 1
    return date(y, m, 1)


def analysis_period(
    silver: pl.DataFrame, cfg: AnalysisCfg, snapshot_date: date | None = None
) -> Period:
    """Últimos `period_months` meses COMPLETOS com dados (ou a janela fixada no config)."""
    if cfg.period_start and cfg.period_end:
        s = date.fromisoformat(cfg.period_start + "-01")
        e = date.fromisoformat(cfg.period_end + "-01")
        return Period(s, e)
    last = silver["mes"].max()
    ref = snapshot_date or date.today()
    current_month = date(ref.year, ref.month, 1)
    if last >= current_month:
        last = _add_months(current_month, -1)
    return Period(_add_months(last, -(cfg.period_months - 1)), last)


# ------------------------------------------------------------ estatística ----
def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cw = np.cumsum(w)
    if cw[-1] <= 0:
        return float(np.median(v))
    idx = int(np.searchsorted(cw, 0.5 * cw[-1]))
    return float(v[min(idx, len(v) - 1)])


def summarize(prices: np.ndarray, qty: np.ndarray, compras: np.ndarray, orgaos: np.ndarray) -> dict:
    p = prices.astype(float)
    _, counts = np.unique(orgaos.astype(str), return_counts=True)
    top_share = float(counts.max() / counts.sum()) if counts.size else 1.0
    mean = float(np.mean(p))
    return {
        "n_registros": int(p.size),
        "n_compras": int(np.unique(compras.astype(str)).size),
        "n_orgaos": int(np.unique(orgaos.astype(str)).size),
        "quantidade": float(np.sum(qty)),
        "mediana": float(np.median(p)),
        "mediana_ponderada": weighted_median(p, qty.astype(float)),
        "p10": float(np.quantile(p, 0.10)),
        "p25": float(np.quantile(p, 0.25)),
        "p75": float(np.quantile(p, 0.75)),
        "p90": float(np.quantile(p, 0.90)),
        "minimo": float(p.min()),
        "maximo": float(p.max()),
        "cv": float(np.std(p, ddof=1) / mean) if p.size > 1 and mean > 0 else None,
        "top_orgao_share": top_share,
    }


def _eligible(row: dict, cfg: AnalysisCfg) -> bool:
    return row["n_compras"] >= cfg.min_purchases_per_uf and row["n_orgaos"] >= cfg.min_buyers_per_uf


# ------------------------------------------------------------ 5.1 item × UF ----
def preco_item_uf(silver: pl.DataFrame, period: Period, cfg: AnalysisCfg) -> pl.DataFrame:
    df = period.filter(silver).filter(pl.col("preco_real").is_not_null())
    rows: list[dict] = []
    for base, sub in (("sem_outliers", df.filter(~pl.col("outlier"))), ("com_outliers", df)):
        for keys, g in sub.group_by(ITEM_COLS, maintain_order=True):
            item = dict(zip(ITEM_COLS, keys, strict=True))
            for uf_key, gg in [
                ("BR", g),
                *[(k[0], v) for k, v in g.group_by(["uf"], maintain_order=True)],
            ]:
                st = summarize(
                    gg["preco_real"].to_numpy(),
                    gg["quantidade_base"].to_numpy(),
                    gg["id_compra"].to_numpy(),
                    gg["codigo_uasg"].fill_null("?").to_numpy(),
                )
                rows.append(
                    {
                        **item,
                        "uf": uf_key,
                        "regiao": None if uf_key == "BR" else gg["regiao"][0],
                        "base": base,
                        "periodo_inicio": period.start,
                        "periodo_fim": period.end,
                        **st,
                        "amostra_suficiente": _eligible(st, cfg),
                        "mes_ref": gg["mes_ref_deflacao"][0],
                    }
                )
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows).sort("codigo_catmat", "base", "uf")


# --------------------------------------------------------- 5.2 dispersão ----
def _cluster_bootstrap_median(
    prices: np.ndarray, clusters: np.ndarray, reps: int, rng: np.random.Generator
) -> np.ndarray:
    """Mediana em reamostragens por conglomerado (compra): sorteia compras com reposição."""
    uniq, inv = np.unique(clusters.astype(str), return_inverse=True)
    groups = [prices[inv == i] for i in range(uniq.size)]
    k = uniq.size
    out = np.empty(reps)
    for r in range(reps):
        pick = rng.integers(0, k, size=k)
        out[r] = np.median(np.concatenate([groups[i] for i in pick]))
    return out


def dispersao_item(
    silver: pl.DataFrame, puf: pl.DataFrame, period: Period, cfg: AnalysisCfg
) -> pl.DataFrame:
    base = period.filter(silver).filter(~pl.col("outlier") & pl.col("preco_real").is_not_null())
    tab = puf.filter(pl.col("base") == "sem_outliers")
    rng = np.random.default_rng(cfg.bootstrap_seed)
    alpha = (1 - cfg.ci_level) / 2
    rows = []
    for keys, g in tab.group_by(ITEM_COLS, maintain_order=True):
        item = dict(zip(ITEM_COLS, keys, strict=True))
        nat = g.filter(pl.col("uf") == "BR").row(0, named=True)
        elig = g.filter((pl.col("uf") != "BR") & pl.col("amostra_suficiente")).sort("mediana")
        row = {
            **item,
            "periodo_inicio": period.start,
            "periodo_fim": period.end,
            "mes_ref": nat["mes_ref"],
            "n_compras_total": nat["n_compras"],
            "n_registros_total": nat["n_registros"],
            "mediana_nacional": nat["mediana"],
            "p90_p10_nacional": nat["p90"] / nat["p10"] if nat["p10"] > 0 else None,
            "n_ufs_com_dados": g.filter(pl.col("uf") != "BR").height,
            "n_ufs_elegiveis": elig.height,
        }
        empty = dict.fromkeys(
            [
                "uf_max", "mediana_max", "n_compras_max", "n_orgaos_max", "top_orgao_share_max",
                "uf_min", "mediana_min", "n_compras_min", "n_orgaos_min", "top_orgao_share_min",
                "razao", "ic_inf", "ic_sup",
            ]
        )  # fmt: skip
        if elig.height < 2:
            rows.append(
                {
                    **row,
                    **empty,
                    "robustez": "sem_comparacao",
                    "motivo_robustez": "menos de 2 UFs com amostra suficiente",
                }
            )
            continue
        lo, hi = elig.row(0, named=True), elig.row(-1, named=True)
        sub = base.filter(pl.col("codigo_catmat") == item["codigo_catmat"])
        g_hi = sub.filter(pl.col("uf") == hi["uf"])
        g_lo = sub.filter(pl.col("uf") == lo["uf"])
        b_hi = _cluster_bootstrap_median(
            g_hi["preco_real"].to_numpy(), g_hi["id_compra"].to_numpy(), cfg.bootstrap_reps, rng
        )
        b_lo = _cluster_bootstrap_median(
            g_lo["preco_real"].to_numpy(), g_lo["id_compra"].to_numpy(), cfg.bootstrap_reps, rng
        )
        ratios = b_hi / b_lo
        ic_inf, ic_sup = np.quantile(ratios, [alpha, 1 - alpha])
        razao = hi["mediana"] / lo["mediana"]
        dominated = (
            hi["top_orgao_share"] > cfg.max_top_buyer_share
            or lo["top_orgao_share"] > cfg.max_top_buyer_share
        )
        if ic_inf > cfg.finding_min_ci_lower and not dominated:
            rob, why = (
                "forte",
                f"IC inferior {ic_inf:.2f} > {cfg.finding_min_ci_lower} e nenhuma UF dominada por um único órgão",
            )
        elif razao > cfg.finding_min_ci_lower and ic_inf > 1.0:
            why = (
                "UF extrema com mediana determinada por um único órgão"
                if dominated
                else f"IC inferior {ic_inf:.2f} abaixo de {cfg.finding_min_ci_lower}"
            )
            rob = "moderado"
        else:
            rob, why = "fraco", "diferença pequena ou IC inclui valores próximos de 1"
        rows.append(
            {
                **row,
                "uf_max": hi["uf"],
                "mediana_max": hi["mediana"],
                "n_compras_max": hi["n_compras"],
                "n_orgaos_max": hi["n_orgaos"],
                "top_orgao_share_max": hi["top_orgao_share"],
                "uf_min": lo["uf"],
                "mediana_min": lo["mediana"],
                "n_compras_min": lo["n_compras"],
                "n_orgaos_min": lo["n_orgaos"],
                "top_orgao_share_min": lo["top_orgao_share"],
                "razao": float(razao),
                "ic_inf": float(ic_inf),
                "ic_sup": float(ic_sup),
                "robustez": rob,
                "motivo_robustez": why,
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).sort("codigo_catmat")


# ------------------------------------------------------------ 5.3 série ----
def serie_item_mes(silver: pl.DataFrame, cfg: AnalysisCfg) -> pl.DataFrame:
    df = silver.filter(~pl.col("outlier"))
    out = (
        df.group_by([*ITEM_COLS, "mes"])
        .agg(
            pl.len().alias("n_registros"),
            pl.col("id_compra").n_unique().alias("n_compras"),
            pl.col("preco_nominal").median().alias("mediana_nominal"),
            pl.col("preco_real").median().alias("mediana_real"),
            pl.col("mes_ref_deflacao").first().alias("mes_ref"),
        )
        .with_columns(
            (pl.col("n_registros") >= cfg.min_obs_month).alias("publicavel"),
            pl.col("n_registros").cast(pl.Int64),
            pl.col("n_compras").cast(pl.Int64),
        )
        .sort("codigo_catmat", "mes")
    )
    return out
