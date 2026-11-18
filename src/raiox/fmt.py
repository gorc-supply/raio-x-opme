"""Formatação de números no padrão brasileiro (R$ 1.234,56; 12,3%; 2,4×)."""

from __future__ import annotations

from datetime import date

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _swap(s: str) -> str:
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def num(v: float | int | None, nd: int = 0) -> str:
    if v is None:
        return "—"
    return _swap(f"{v:,.{nd}f}")


def brl(v: float | None, nd: int = 2) -> str:
    if v is None:
        return "—"
    return f"R$ {num(v, nd)}"


def brl_compact(v: float | None) -> str:
    """R$ 1,2 mil / R$ 3,4 mi / R$ 5,6 bi."""
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"R$ {num(v / 1e9, 1)} bi"
    if a >= 1e6:
        return f"R$ {num(v / 1e6, 1)} mi"
    if a >= 1e4:
        return f"R$ {num(v / 1e3, 1)} mil"
    return brl(v, 0 if a >= 100 else 2)


def usd_compact(v: float | None) -> str:
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"US$ {num(v / 1e9, 1)} bi"
    if a >= 1e6:
        return f"US$ {num(v / 1e6, 1)} mi"
    if a >= 1e3:
        return f"US$ {num(v / 1e3, 1)} mil"
    return f"US$ {num(v, 0)}"


def pct(v: float | None, nd: int = 1) -> str:
    """Recebe fração (0,123) e devolve '12,3%'.

    Arredondamento nunca esconde a informação: um valor diferente de zero nunca aparece
    como "0%" e um valor diferente de 100% nunca aparece como "100%". Abaixo de 1% usa
    ao menos uma casa decimal; se ainda assim arredondar para zero, vira "menos de 0,1%".
    """
    if v is None:
        return "—"
    p = v * 100
    a = abs(p)
    if 0 < a < 1:
        nd = max(nd, 1)
        if round(a, nd) == 0:
            return f"menos de {num(10.0**-nd, nd)}%"
    elif a != 100 and round(a, nd) == 100:
        nd = max(nd, 1)
        if round(a, nd) == 100:
            return f"mais de {num(100 - 10.0**-nd, nd)}%" if a < 100 else "pouco mais de 100%"
    return f"{num(p, nd)}%"


def ratio(v: float | None, nd: int = 1) -> str:
    if v is None:
        return "—"
    return f"{num(v, nd)}×"


def month(d: date | None) -> str:
    """date(2026, 10, 1) → 'out/2026'."""
    if d is None:
        return "—"
    return f"{MESES[d.month - 1]}/{d.year}"
