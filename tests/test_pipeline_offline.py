"""Pipeline inteiro no modo offline (só fixtures; nenhuma chamada de rede)."""

import json
import os

import polars as pl
import pytest

from raiox.config import get_settings
from raiox.pipeline import CORE_SOURCES, run_analyze, run_ingest, run_quality, run_transform
from raiox.schemas import FORBIDDEN_WORDS


@pytest.fixture(scope="module")
def offline_gold():
    os.environ["RAIOX_OFFLINE"] = "1"
    try:
        s = get_settings(offline=True)
        run_ingest(s, [*CORE_SOURCES, "complementares"])
        run_transform(s)
        run_quality(s)
        run_analyze(s)
        yield s
    finally:
        os.environ.pop("RAIOX_OFFLINE", None)


def test_offline_writes_only_to_offline_dir(offline_gold):
    gold = offline_gold.path("gold")
    assert "offline" in gold.parts
    assert (gold / "preco_item_uf.parquet").exists()


def test_offline_gold_tables_are_consistent(offline_gold):
    gold = offline_gold.path("gold")
    puf = pl.read_parquet(gold / "preco_item_uf.parquet")
    assert puf.height > 0
    assert (puf["p10"] <= puf["mediana"]).all() and (puf["mediana"] <= puf["p90"]).all()
    meta = json.loads((gold / "meta.json").read_text(encoding="utf-8"))
    assert meta["n_itens"] >= 4
    imp = pl.read_parquet(gold / "importacao_ncm_ano.parquet")
    mp = imp.filter(pl.col("ncm") == "90215000")
    assert mp["preco_cif_usd_unid"][0] > 0  # marca-passo tem unidade estatística em peças
    assert imp.filter(pl.col("ncm") == "90219012")["preco_cif_usd_unid"][0] is None  # stent: kg


def test_offline_findings_respect_communication_rules(offline_gold):
    ach = pl.read_parquet(offline_gold.path("gold") / "achados.parquet")
    assert ach.height > 0
    for frase in ach["frase"].to_list():
        assert not any(w in frase.lower() for w in FORBIDDEN_WORDS)
    assert ach["periodo"].str.len_chars().min() > 0
    assert ach["fonte"].str.len_chars().min() > 0


def test_no_full_cpf_in_silver(offline_gold):
    sv = pl.read_parquet(offline_gold.path("silver") / "compras_precos.parquet")
    assert not sv["ni_fornecedor"].drop_nulls().str.contains(r"^\d{11}$").any()


def test_pipeline_is_idempotent(offline_gold):
    gold = offline_gold.path("gold")
    before = {p.name: pl.read_parquet(p) for p in gold.glob("*.parquet")}
    meta_before = (gold / "meta.json").read_text(encoding="utf-8")
    run_analyze(offline_gold)
    after = {p.name: pl.read_parquet(p) for p in gold.glob("*.parquet")}
    assert before.keys() == after.keys()
    for name, df in before.items():
        assert df.equals(after[name]), f"{name} mudou entre duas execuções"
    assert meta_before == (gold / "meta.json").read_text(encoding="utf-8")
