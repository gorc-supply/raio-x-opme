"""Paleta: contraste WCAG AA e paleta categórica distinguível com daltonismo."""

import pytest

from raiox.viz import theme


@pytest.mark.parametrize(
    "row", theme.contrast_report(), ids=lambda r: f"{r['uso']} {r['cor']}/{r['fundo']}"
)
def test_contrast_meets_wcag_aa(row):
    assert row["razao"] >= row["minimo"], row


@pytest.mark.parametrize("kind", [None, "protanopia", "deuteranopia", "tritanopia"])
def test_categorical_palette_is_colorblind_safe(kind):
    # ΔE (CIE76) mínimo entre quaisquer duas cores, na visão simulada (Machado et al., 2009).
    assert theme.min_delta_e(theme.CATEGORICAL, kind) >= 10
    assert theme.min_delta_e(theme.CATEGORICAL_DARK, kind) >= 8


def test_palette_shape_and_map_scale():
    assert len(theme.CATEGORICAL) == 6 and len(set(theme.CATEGORICAL)) == 6
    assert theme.SEQUENTIAL[0] == "#DCEFF1" and theme.SEQUENTIAL[-1] == "#0E6E7E"
    assert theme.ROBUSTEZ["forte"] == "#E07A5F"


def test_plotly_template_uses_brazilian_separators():
    tpl = theme.plotly_template()
    assert tpl["layout"]["separators"] == ",."
    assert tpl["layout"]["paper_bgcolor"] == "rgba(0,0,0,0)"
    assert tpl["layout"]["colorway"] == theme.CATEGORICAL
