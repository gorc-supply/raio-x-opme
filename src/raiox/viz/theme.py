"""Identidade visual única para painel (plotly) e gráficos estáticos (matplotlib).

Paleta acessível: categórica Okabe-Ito (segura para daltonismo) e uma escala
sequencial azul para mapas. Cores de destaque com contraste AA sobre fundo claro.
"""

from __future__ import annotations

INK = "#1F2933"  # texto principal
MUTED = "#52606D"  # texto secundário
GRID = "#E4E7EB"
BG = "#FFFFFF"
SURFACE = "#F5F7FA"
PRIMARY = "#0B5D7A"  # azul-petróleo
ACCENT = "#C2410C"  # laranja queimado (destaque "mais caro")
LOW = "#0E7490"  # azul-ciano (destaque "mais barato")
INSUFFICIENT = "#D3D6DB"  # amostra insuficiente (cinza claro)

CATEGORICAL = [
    "#0072B2",
    "#E69F00",
    "#009E73",
    "#CC79A7",
    "#56B4E9",
    "#D55E00",
    "#F0E442",
    "#000000",
]
SEQUENTIAL = ["#E6F0F5", "#B9D4E2", "#7FB1CB", "#3F87AE", "#0B5D7A", "#073B4F"]

FONT_FAMILY = "Inter, Segoe UI, Roboto, Helvetica, Arial, sans-serif"


def plotly_layout(**overrides) -> dict:
    base = {
        "font": {"family": FONT_FAMILY, "color": INK, "size": 13},
        "paper_bgcolor": BG,
        "plot_bgcolor": BG,
        "colorway": CATEGORICAL,
        "margin": {"l": 10, "r": 10, "t": 40, "b": 10},
        "hoverlabel": {"font": {"family": FONT_FAMILY}},
        "separators": ",.",  # vírgula decimal, ponto de milhar
    }
    base.update(overrides)
    return base


def mpl_rc() -> dict:
    return {
        "font.family": "DejaVu Sans",
        "font.size": 15,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "axes.titlecolor": INK,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 1.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.prop_cycle": __import__("cycler").cycler(color=CATEGORICAL),
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "savefig.facecolor": BG,
    }
