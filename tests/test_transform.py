from datetime import date

import polars as pl
import pytest

from raiox.config import get_settings
from raiox.transform.deflate import deflate, ipca_index
from raiox.transform.normalize import deduplicate, is_cpf, mask_cpf, norm_text, silver_compras
from raiox.transform.outliers import flag_outliers
from raiox.transform.units import base_unit_of, normalize_units

CFG = get_settings(offline=False).analysis


# ------------------------------------------------------------- unidades ----
def _units_df(rows):
    return pl.DataFrame(
        rows,
        schema={
            "siglaUnidadeFornecimento": pl.String,
            "nomeUnidadeFornecimento": pl.String,
            "siglaUnidadeMedida": pl.String,
            "capacidadeUnidadeFornecimento": pl.Float64,
            "precoUnitario": pl.Float64,
            "quantidade": pl.Float64,
        },
        orient="row",
    )


def test_units_piece_with_zero_capacity_is_factor_one():
    out = normalize_units(_units_df([("UN", "UNIDADE", None, 0.0, 500.0, 10.0)]), CFG)
    r = out.row(0, named=True)
    assert r["unidade_base"] == "UN"
    assert r["fator_unidade"] == 1.0
    assert r["preco_unidade_base"] == 500.0
    assert r["motivo_descarte_unidade"] is None


def test_units_box_with_capacity_divides_price():
    out = normalize_units(_units_df([("CX", "CAIXA", "UN", 10.0, 1000.0, 2.0)]), CFG)
    r = out.row(0, named=True)
    assert r["unidade_base"] == "UN"
    assert r["preco_unidade_base"] == pytest.approx(100.0)
    assert r["quantidade_base"] == pytest.approx(20.0)
    assert r["motivo_descarte_unidade"] is None


def test_units_unsafe_cases_are_discarded_with_reason():
    out = normalize_units(
        _units_df(
            [
                (None, None, None, 0.0, 10.0, 1.0),  # sem unidade
                ("UN", "UNIDADE", None, 5.0, 10.0, 1.0),  # UN com capacidade > 1
                ("CX", "CAIXA", None, 10.0, 10.0, 1.0),  # caixa sem unidade de medida
                ("CX", "CAIXA", "UN", 0.0, 10.0, 1.0),  # caixa sem capacidade
                ("XYZ", "XYZ", None, 0.0, 10.0, 1.0),  # desconhecida
            ]
        ),
        CFG,
    )
    assert out["motivo_descarte_unidade"].to_list() == [
        "unidade_ausente",
        "capacidade_ambigua",
        "embalagem_sem_unidade_medida",
        "embalagem_sem_capacidade",
        "unidade_desconhecida",
    ]


def test_units_name_used_when_sigla_missing_and_kit_is_set():
    out = normalize_units(
        _units_df([(None, "UNIDADE", None, 0.0, 1.0, 1.0), ("KIT", "KIT", None, 1.0, 1.0, 1.0)]),
        CFG,
    )
    assert out["unidade_base"].to_list() == ["UN", "CONJUNTO"]
    assert base_unit_of("kit", CFG) == "CONJUNTO"
    assert base_unit_of("UN", CFG) == "UN"


# -------------------------------------------------------------- deflação ----
def test_ipca_index_and_deflation_to_last_month():
    ipca = pl.DataFrame(
        {
            "mes": [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
            "variacao_pct": [1.0, 0.0, 2.0],
        }
    )
    idx = ipca_index(ipca)
    assert idx["indice"].to_list() == pytest.approx([1.01, 1.01, 1.0302])
    df = pl.DataFrame(
        {
            "mes": [date(2026, 1, 1), date(2026, 3, 1), date(2026, 4, 1), date(2025, 1, 1)],
            "v": [100.0, 100.0, 100.0, 100.0],
        }
    )
    out = deflate(df, "mes", ["v"], idx)
    vals = out["v_real"].to_list()
    assert vals[0] == pytest.approx(102.0)  # jan → mar: só a inflação de fev e mar
    assert vals[1] == pytest.approx(100.0)  # mês de referência
    assert vals[2] == pytest.approx(100.0)  # depois do último IPCA: fator 1
    assert vals[3] is None  # antes do início do índice: não deflacionável
    assert out["mes_ref_deflacao"][0] == date(2026, 3, 1)


# --------------------------------------------------------------- outliers ----
def test_outliers_flagged_not_removed():
    prices = [100.0, 102, 98, 101, 99, 103, 97, 100, 5000.0, 1.0]
    df = pl.DataFrame({"g": ["a"] * len(prices), "p": prices})
    out = flag_outliers(df, "p", ["g"], iqr_k=3.0, mad_z=3.5, min_n=8)
    assert out.height == df.height  # nada apagado
    flagged = out.filter(pl.col("outlier"))["p"].to_list()
    assert sorted(flagged) == [1.0, 5000.0]
    assert out.filter(pl.col("p") == 5000.0)["outlier_iqr"][0]


def test_outliers_small_groups_are_not_flagged():
    df = pl.DataFrame({"g": ["a"] * 4, "p": [1.0, 2.0, 3.0, 1000.0]})
    out = flag_outliers(df, "p", ["g"], iqr_k=3.0, mad_z=3.5, min_n=8)
    assert not out["outlier"].any()


# ------------------------------------------------------------ LGPD / texto ----
@pytest.mark.parametrize(
    ("ni", "expected"),
    [
        ("12345678901", "***.456.789-**"),
        ("123.456.789-01", "***.456.789-**"),
        ("29182018000133", "29182018000133"),
        ("***.456.789-**", "***.456.789-**"),  # idempotente
        (None, None),
    ],
)
def test_mask_cpf(ni, expected):
    assert mask_cpf(ni) == expected


def test_is_cpf_and_norm_text():
    assert is_cpf("123.456.789-01")
    assert is_cpf("***.456.789-**")
    assert not is_cpf("29182018000133")
    assert norm_text("  Prótese   de joelho ") == "PROTESE DE JOELHO"
    assert norm_text("") is None


# --------------------------------------------------------------- dedup ----
def test_deduplicate_keeps_latest_update():
    df = pl.DataFrame(
        {
            "idCompra": ["1", "1", "2"],
            "idItemCompra": [10, 10, 20],
            "codigoItemCatalogo": [5, 5, 5],
            "dataHoraAtualizacaoItem": [
                "2026-01-01T00:00:00",
                "2026-02-01T00:00:00",
                "2026-01-01T00:00:00",
            ],
            "precoUnitario": [100.0, 120.0, 50.0],
        }
    )
    out, removed = deduplicate(df)
    assert removed == 1
    assert out.filter(pl.col("idCompra") == "1")["precoUnitario"][0] == 120.0


# ---------------------------------------------------- silver de compras ----
def _bronze_row(**kw):
    base = {
        "idCompra": "1",
        "idItemCompra": 1,
        "idCompraItem": "x",
        "codigoItemCatalogo": 999,
        "descricaoItem": "ITEM",
        "dataCompra": "2026-02-10",
        "dataHoraAtualizacaoItem": "2026-02-11T00:00:00",
        "estado": "SP",
        "codigoMunicipio": 1,
        "municipio": "X",
        "codigoUasg": "100",
        "nomeUasg": "HOSP",
        "codigoOrgao": 1,
        "nomeOrgao": "ORG",
        "esfera": "F",
        "poder": "E",
        "forma": "SISRP",
        "modalidade": 5,
        "niFornecedor": "12345678901",
        "nomeFornecedor": "Fulano de Tal",
        "marca": "Marca",
        "siglaUnidadeFornecimento": "UN",
        "nomeUnidadeFornecimento": "UNIDADE",
        "capacidadeUnidadeFornecimento": 0.0,
        "siglaUnidadeMedida": None,
        "quantidade": 2.0,
        "precoUnitario": 100.0,
        "_snapshot": "2026-03-01",
        "_fetched_at": "2026-03-01T00:00:00",
    }
    base.update(kw)
    return base


def test_silver_compras_masks_cpf_and_counts_discards():
    rows = [
        _bronze_row(),
        _bronze_row(idCompra="2", idItemCompra=2, precoUnitario=0.0),
        _bronze_row(idCompra="3", idItemCompra=3, estado="XX"),
        _bronze_row(idCompra="4", idItemCompra=4, codigoItemCatalogo=1),
    ]
    bronze = pl.DataFrame(rows)
    catalog = [
        {
            "codigo_catmat": 999,
            "nome_curto": "Item",
            "familia": "F",
            "familia_macro": "M",
            "ncm": "1",
            "unidade_dominante": "UN",
        }
    ]
    ufs = pl.DataFrame({"uf": ["SP"], "regiao": ["Sudeste"]})
    idx = ipca_index(pl.DataFrame({"mes": [date(2026, 2, 1)], "variacao_pct": [0.5]}))
    silver, discards, counts = silver_compras(bronze, catalog, ufs, idx, CFG)
    assert silver.height == 1
    assert silver["ni_fornecedor"][0] == "***.456.789-**"
    assert silver["fornecedor"][0] == "PESSOA FISICA"
    assert counts["descarte_preco_invalido"] == 1
    assert counts["descarte_uf_invalida"] == 1
    assert counts["descarte_fora_do_catalogo"] == 1
    assert set(discards["motivo_descarte"]) == {"preco_invalido", "uf_invalida", "fora_do_catalogo"}


def test_bronze_masks_pf_suppliers():
    from raiox.sources.compras import mask_pf_suppliers

    df = pl.DataFrame(
        {
            "niFornecedor": ["12345678901", "29182018000133", None],
            "nomeFornecedor": ["Fulano", "Empresa SA", None],
        }
    )
    out = mask_pf_suppliers(df)
    assert out["niFornecedor"].to_list() == ["***.456.789-**", "29182018000133", None]
    assert out["nomeFornecedor"].to_list() == ["PESSOA FISICA", "Empresa SA", None]
