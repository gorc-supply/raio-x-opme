from datetime import date

import numpy as np
import polars as pl
import pytest

from raiox import fmt
from raiox.analytics.concentration import cr, fornecedores_item, hhi
from raiox.analytics.dispersion import (
    Period,
    _cluster_bootstrap_median,
    analysis_period,
    dispersao_item,
    preco_item_uf,
    serie_item_mes,
    summarize,
    weighted_median,
)
from raiox.config import get_settings
from raiox.schemas import SchemaFailure, check_language

S = get_settings(offline=False)
CFG = S.analysis


def _silver(rows):
    """rows: (uf, id_compra, uasg, preco)"""
    data = []
    for i, (uf, compra, uasg, preco) in enumerate(rows):
        data.append(
            {
                "codigo_catmat": 1,
                "nome_curto": "Item",
                "familia": "F",
                "familia_macro": "M",
                "unidade_base": "UN",
                "uf": uf,
                "regiao": "R",
                "id_compra": str(compra),
                "id_item_compra": i,
                "codigo_uasg": str(uasg),
                "preco_real": float(preco),
                "preco_nominal": float(preco),
                "quantidade_base": 1.0,
                "mes": date(2026, 1, 1),
                "data_compra": date(2026, 1, 10),
                "mes_ref_deflacao": date(2026, 1, 1),
                "outlier": False,
                "fornecedor": f"F{compra % 3}",
                "marca": "M",
                "snapshot": "2026-02-15",
            }
        )
    return pl.DataFrame(data)


PERIOD = Period(date(2025, 2, 1), date(2026, 1, 1))


def test_weighted_median_and_summarize():
    assert weighted_median(np.array([1.0, 2.0, 100.0]), np.array([1.0, 1.0, 10.0])) == 100.0
    st = summarize(
        np.array([10.0, 20.0, 30.0]),
        np.ones(3),
        np.array(["a", "b", "b"]),
        np.array(["x", "x", "y"]),
    )
    assert st["mediana"] == 20.0
    assert st["n_compras"] == 2
    assert st["n_orgaos"] == 2
    assert st["top_orgao_share"] == pytest.approx(2 / 3)


def test_eligibility_requires_purchases_and_buyers():
    rows = [("SP", c, c % 3, 100) for c in range(6)] + [("RJ", 100 + c, 7, 100) for c in range(6)]
    puf = preco_item_uf(_silver(rows), PERIOD, CFG)
    sp = puf.filter((pl.col("uf") == "SP") & (pl.col("base") == "sem_outliers")).row(0, named=True)
    rj = puf.filter((pl.col("uf") == "RJ") & (pl.col("base") == "sem_outliers")).row(0, named=True)
    assert sp["amostra_suficiente"]
    assert not rj["amostra_suficiente"]  # um único órgão
    assert set(puf["uf"]) == {"SP", "RJ", "BR"}


def test_strong_dispersion_requires_ci_and_no_dominance():
    rng = np.random.default_rng(1)
    rows = [("SP", c, c % 4, 1000 * rng.uniform(0.95, 1.05)) for c in range(12)]
    rows += [("RJ", 100 + c, 10 + c % 4, 300 * rng.uniform(0.95, 1.05)) for c in range(12)]
    sv = _silver(rows)
    puf = preco_item_uf(sv, PERIOD, CFG)
    disp = dispersao_item(sv, puf, PERIOD, CFG).row(0, named=True)
    assert disp["uf_max"] == "SP" and disp["uf_min"] == "RJ"
    assert disp["razao"] == pytest.approx(1000 / 300, rel=0.1)
    assert disp["ic_inf"] > 1.5
    assert disp["p90_p10_nacional"] < CFG.max_p90_p10_homogeneo
    assert disp["robustez"] == "forte"
    # Com uma trava de homogeneidade mais rígida, o mesmo caso cai para "moderado".
    strict = CFG.model_copy(update={"max_p90_p10_homogeneo": 2.0})
    d2 = dispersao_item(sv, puf, PERIOD, strict).row(0, named=True)
    assert d2["robustez"] == "moderado"
    assert "heterogêneo" in d2["motivo_robustez"]


def test_dispersion_without_two_eligible_ufs():
    rows = [("SP", c, c % 3, 100) for c in range(6)]
    sv = _silver(rows)
    disp = dispersao_item(sv, preco_item_uf(sv, PERIOD, CFG), PERIOD, CFG)
    assert disp["robustez"][0] == "sem_comparacao"


def test_bootstrap_is_deterministic_with_seed():
    p = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    c = np.array(["a", "b", "c", "d", "e"])
    a = _cluster_bootstrap_median(p, c, 200, np.random.default_rng(42))
    b = _cluster_bootstrap_median(p, c, 200, np.random.default_rng(42))
    assert np.array_equal(a, b)


def test_analysis_period_excludes_snapshot_month():
    sv = _silver([("SP", 1, 1, 10)]).with_columns(pl.lit(date(2026, 2, 1)).alias("mes"))
    p = analysis_period(sv, CFG)
    assert p.end == date(2026, 1, 1)
    assert p.start == date(2024, 2, 1)
    assert p.label == "02/2024 a 01/2026"


def test_serie_item_mes():
    sv = _silver([("SP", c, c, 100 + c) for c in range(5)])
    out = serie_item_mes(sv, CFG)
    assert out.height == 1
    assert out["mediana_real"][0] == 102.0
    assert out["publicavel"][0]


def test_hhi_and_concentration():
    assert hhi([1.0]) == 10000
    assert hhi([0.5, 0.5]) == 5000
    assert cr([0.5, 0.3, 0.1, 0.1], 3) == pytest.approx(0.9)
    sv = _silver([("SP", c, c, 100) for c in range(6)])
    f = fornecedores_item(sv, PERIOD, 3)
    forn = f.filter(pl.col("tipo") == "fornecedor")
    assert forn["participacao_valor"].sum() == pytest.approx(1.0)
    assert forn["hhi"][0] == pytest.approx(3 * (100 / 3) ** 2)


def test_language_guardrail():
    check_language(["Diferença de preço que merece investigação."])
    with pytest.raises(SchemaFailure):
        check_language(["Indício de superfaturamento"])


def test_brazilian_formatting():
    assert fmt.brl(1234.5) == "R$ 1.234,50"
    assert fmt.pct(0.123) == "12,3%"
    assert fmt.ratio(2.345) == "2,3×"
    assert fmt.month(date(2026, 10, 1)) == "out/2026"
    assert fmt.usd_compact(92_482_020) == "US$ 92,5 mi"
    assert fmt.brl(None) == "—"
