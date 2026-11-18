"""SIGTAP: parser de largura fixa, seleção de competências, mapa e junção com o preço praticado."""

import io
import zipfile
from datetime import date

import polars as pl
import pytest

from raiox.analytics.dispersion import Period
from raiox.analytics.findings import _sigtap_findings, sigtap_note
from raiox.analytics.sigtap_bridge import format_code, parse_mapping, ponte_sigtap_preco
from raiox.config import get_settings
from raiox.sources import sigtap

# Layouts reais (cabeçalhos copiados dos ZIPs de 01/2015 e 11/2026): VL_SH mudou de 10 para 12.
LAYOUT_2015 = """Coluna,Tamanho,Inicio,Fim,Tipo
CO_PROCEDIMENTO,10,1,10,VARCHAR2
NO_PROCEDIMENTO,250,11,260,VARCHAR2
VL_SH,10,261,270,NUMBER
VL_SA,10,271,280,NUMBER
VL_SP,10,281,290,NUMBER
CO_FINANCIAMENTO,2,291,292,VARCHAR2
DT_COMPETENCIA,6,293,298,CHAR
"""
LAYOUT_2026 = (
    LAYOUT_2015.replace("VL_SH,10,261,270", "VL_SH,12,261,272")
    .replace("VL_SA,10,271,280", "VL_SA,12,273,284")
    .replace("VL_SP,10,281,290", "VL_SP,12,285,296")
    .replace("CO_FINANCIAMENTO,2,291,292", "CO_FINANCIAMENTO,2,297,298")
    .replace("DT_COMPETENCIA,6,293,298", "DT_COMPETENCIA,6,299,304")
)


def _line(code: str, name: str, sh: int, width: int, comp: str) -> str:
    return code + name.ljust(250) + str(sh).zfill(width) + "0" * width + "0" * width + "06" + comp


def _zip(layout: str, lines: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("tb_procedimento_layout.txt", layout.encode("latin1"))
        zf.writestr("tb_procedimento.txt", "\r\n".join(lines).encode("latin1"))
    return buf.getvalue()


def test_parse_layout_rejects_inconsistent_sizes():
    with pytest.raises(ValueError):
        sigtap.parse_layout("Coluna,Tamanho,Inicio,Fim,Tipo\nVL_SH,12,1,10,NUMBER\n")
    with pytest.raises(ValueError):
        sigtap.parse_layout("sem cabeçalho\n")


@pytest.mark.parametrize(
    ("layout", "width", "comp"), [(LAYOUT_2015, 10, "201501"), (LAYOUT_2026, 12, "202611")]
)
def test_fixed_width_parser_reads_both_layouts_and_accents(tmp_path, layout, width, comp):
    lines = [
        _line("0702040614", "STENT FARMACOLÓGICO PARA ARTERIA CORONARIA", 203450, width, comp),
        _line("0702030244", "COMPONENTE PATELAR CIMENTADO / FIXAÇÃO", 34546, width, comp),
        _line("0101010010", "ATIVIDADE EDUCATIVA / ORIENTAÇÃO", 0, width, comp),  # grupo 01: sai
    ]
    path = tmp_path / f"TabelaUnificada_{comp}_v1.zip"
    path.write_bytes(_zip(layout, lines))
    df = sigtap.read_procedures(path)
    assert df["codigo_sigtap"].to_list() == ["0702040614", "0702030244"]
    # Acentos em latin-1 não deslocam as colunas: valor em centavos → reais.
    assert df["valor_sh"].to_list() == [2034.50, 345.46]
    assert df["descricao_sigtap"][0] == "STENT FARMACOLÓGICO PARA ARTERIA CORONARIA"
    assert df["competencia"].unique().to_list() == [comp]
    assert df["co_financiamento"].unique().to_list() == ["06"]


def test_select_competences_one_per_year_plus_latest_and_newest_version():
    names = [
        "TabelaUnificada_201412_v1.zip",
        "TabelaUnificada_201501_v1.zip",
        "TabelaUnificada_201501_v2.zip",  # versão mais nova da mesma competência
        "TabelaUnificada_201502_v1.zip",
        "TabelaUnificada_201603_v1.zip",  # sem janeiro em 2016: pega o mês mais próximo
        "TabelaUnificada_201611_v1.zip",
        "TabelaUnificada_201711_v1.zip",  # mais recente
        "Mapeamento_TUSS_SIGTAP.zip",
        "leia-me.txt",
    ]
    out = sigtap.select_competences(sigtap.parse_listing(names), start_year=2015)
    assert out["competencia"].to_list() == ["201501", "201603", "201711"]
    assert out.filter(pl.col("competencia") == "201501")["versao"][0] == "2"


def _mapping(**over):
    pair = {
        "codigo_sigtap": "0702040614",
        "descricao_sigtap": "STENT",
        "codigo_catmat": 476772,
        "familia": "Stent",
        "confianca": "alta",
        "justificativa": "teste",
    }
    pair.update(over)
    return {"validado_por_gabriel": False, "pares": [pair]}


def test_mapping_validation():
    m = parse_mapping(_mapping())
    assert m.validated is False and m.pairs.height == 1
    with pytest.raises(ValueError):
        parse_mapping(_mapping(confianca="certeza"))
    with pytest.raises(ValueError):
        parse_mapping(_mapping(codigo_sigtap="07020406"))
    with pytest.raises(ValueError):
        parse_mapping(_mapping(justificativa=""))
    dup = _mapping()
    dup["pares"] = dup["pares"] * 2
    with pytest.raises(ValueError):
        parse_mapping(dup)


def test_format_code():
    assert format_code("0702040614") == "07.02.04.061-4"


def _sigtap_silver():
    from raiox.transform.deflate import deflate

    index = pl.DataFrame({"mes": [date(2015, 1, 1), date(2026, 10, 1)], "indice": [1.0, 2.0]})
    df = pl.DataFrame(
        {
            "codigo_sigtap": ["0702040614", "0702040614"],
            "descricao_sigtap": ["STENT", "STENT"],
            "competencia": ["201501", "202611"],
            "mes_competencia": [date(2015, 1, 1), date(2026, 11, 1)],
            "valor_opme": [1000.0, 1000.0],
        }
    )
    return deflate(df, "mes_competencia", ["valor_opme"], index)


def _purchases(prices):
    n = len(prices)
    return pl.DataFrame(
        {
            "codigo_catmat": [476772] * n,
            "nome_curto": ["Stent X"] * n,
            "id_compra": [str(i) for i in range(n)],
            "codigo_uasg": [str(i % 4) for i in range(n)],
            "mes": [date(2026, 1, 1)] * n,
            "preco_real": prices,
            "outlier": [False] * (n - 1) + [True],
        }
    )


def test_ponte_sigtap_joins_price_median_and_table_value():
    sv = _sigtap_silver()
    # IPCA dobra entre 2015 e out/2026: o valor nominal constante perde metade do valor real.
    assert sv["valor_opme_real"].to_list() == [2000.0, 1000.0]
    comp = _purchases([1500.0] * 20 + [99999.0])  # o outlier fica de fora
    period = Period(date(2025, 11, 1), date(2026, 10, 1))
    out = ponte_sigtap_preco(sv, comp, period, parse_mapping(_mapping()), 200, 1, 0.95)
    r = out.row(0, named=True)
    assert r["competencia_sigtap"] == "202611"
    assert r["valor_sigtap_nominal"] == 1000.0
    assert r["mediana_preco_real"] == 1500.0
    assert r["razao_preco_sigtap"] == pytest.approx(1.5)
    assert r["n_compras"] == 20 and r["n_orgaos"] == 4
    assert r["valor_sigtap_mais_antigo_real"] == 2000.0
    assert r["mapa_validado"] is False


def test_sigtap_note_follows_the_direction_of_the_difference():
    assert "defasagem" in sigtap_note(1.2, 1.8)
    assert "cobre" in sigtap_note(0.2, 0.4)
    assert "em linha" in sigtap_note(0.9, 1.1)


@pytest.mark.parametrize(("validated", "expected"), [(False, "moderado"), (True, "forte")])
def test_ratio_finding_is_forte_only_with_validated_mapping(validated, expected):
    sv = _sigtap_silver()
    comp = _purchases([1500.0] * 40 + [99999.0])  # 40 compras, IC bem acima de 1,1
    period = Period(date(2025, 11, 1), date(2026, 10, 1))
    data = _mapping()
    data["validado_por_gabriel"] = validated
    ponte = ponte_sigtap_preco(sv, comp, period, parse_mapping(data), 200, 1, 0.95)
    ach = [
        a
        for a in _sigtap_findings(ponte, get_settings(offline=True), "out/2026")
        if a["tipo"] == "ponte_sigtap"
    ]
    assert len(ach) == 1
    assert ach[0]["robustez"] == expected
    assert ("ainda não validado" in ach[0]["motivo_robustez"]) is (not validated)
