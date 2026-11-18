"""Formatação de percentuais: o arredondamento nunca pode esconder a informação."""

import re

import pytest

from raiox import fmt


@pytest.mark.parametrize(
    ("value", "nd", "expected"),
    [
        (0.123, 1, "12,3%"),
        (0.5, 0, "50%"),
        (0.0, 0, "0%"),
        (1.0, 0, "100%"),
        # Abaixo de 1%: sempre uma casa decimal, nunca "0%" nem "1%".
        (0.0012, 0, "0,1%"),
        (0.007, 0, "0,7%"),
        (0.0012, 1, "0,1%"),
        (0.0004, 0, "menos de 0,1%"),
        (0.0004, 1, "menos de 0,1%"),
        (0.00004, 2, "menos de 0,01%"),
        # Perto de 100%: "100%" só quando é exatamente 100%.
        (0.996, 0, "99,6%"),
        (0.9996, 0, "mais de 99,9%"),
        (1.003, 0, "100,3%"),
        (1.0004, 1, "pouco mais de 100%"),
        # Negativos e valores grandes seguem o padrão.
        (-0.36, 0, "-36%"),
        (1.8, 0, "180%"),
        (None, 0, "—"),
    ],
)
def test_pct_never_hides_information(value, nd, expected):
    assert fmt.pct(value, nd) == expected


@pytest.mark.parametrize("value", [1e-9, 0.0001, 0.0049, 0.0051, 0.0099, 0.9951, 0.99999, 1.00001])
def test_pct_nonzero_never_shows_zero_or_hundred(value):
    for nd in (0, 1, 2):
        out = fmt.pct(value, nd)
        assert not re.fullmatch(r"-?0(,0+)?%", out), out
        assert not re.fullmatch(r"100(,0+)?%", out), out
