"""Identidade visual única: painel (Streamlit + CSS), gráficos do painel (Plotly) e do
LinkedIn (matplotlib). Toda cor do projeto sai daqui.

Paleta "hospitalar": azul-petróleo como primária, fundo cinza-azulado claro, coral para
achados fortes. Contraste checado por `contrast_report()` (WCAG 2.1: texto ≥ 4,5:1,
texto grande e elementos gráficos ≥ 3:1) e paleta categórica testada para daltonismo
(simulação de Machado et al., 2009) — ver tests/test_theme.py e docs/DECISOES.md.
"""

from __future__ import annotations

import itertools
import math

# ----------------------------------------------------------------- claro ----
PAGE_BG = "#F4F7FA"  # fundo da página
CARD_BG = "#FFFFFF"  # cards, tabelas, expanders
SIDEBAR_BG = "#E9EFF5"  # barra lateral
PRIMARY = "#0E6E7E"  # azul-petróleo (tom hospitalar)
DARK = "#12304A"  # títulos e cabeçalho
INK = "#1B2B3A"  # texto
MUTED = "#5B6B7B"  # texto secundário
BORDER = "#D5DEE7"  # bordas finas
GRID = "#E3E9EF"  # grade dos gráficos
GRID_DARK = "#9AA7B4"  # traços de intervalo de confiança

# Robustez dos achados (borda dos cards, selos). Texto sobre elas: DARK.
FORTE = "#E07A5F"  # coral
MODERADO = "#F2B544"
FRACO = "#B8C2CC"
ROBUSTEZ = {"forte": FORTE, "moderado": MODERADO, "fraco": FRACO, "sem_comparacao": FRACO}

# Marcas nos gráficos (≥ 3:1 sobre o fundo; coral escuro = mesmo matiz do FORTE).
ACCENT = "#C4573A"  # mais caro / acima da tabela / importação
LOW = "#4255B5"  # mais barato / abaixo da tabela / exportação
INSUFFICIENT = FRACO  # UF com amostra insuficiente no mapa

# Categórica (até 6 séries): segura para daltonismo e ≥ 3:1 sobre PAGE_BG e CARD_BG.
CATEGORICAL = ["#0E6E7E", "#C4573A", "#4255B5", "#B03A7A", "#7A6A00", "#12304A"]


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ra, rb, strict=True))


# Escala sequencial do mapa: #DCEFF1 → #0E6E7E (6 tons, interpolados mais abaixo).
SEQ_START, SEQ_END = "#DCEFF1", PRIMARY

# --------------------------------------------------------------- escuro ----
DARK_MODE = {
    "PAGE_BG": "#0E1A24",
    "CARD_BG": "#15263A",
    "SIDEBAR_BG": "#112131",
    "PRIMARY": "#5EC2CF",
    "DARK": "#E7EEF5",
    "INK": "#E7EEF5",
    "MUTED": "#A9B8C6",
    "BORDER": "#2A3F55",
    "GRID": "#24384C",
    "GRID_DARK": "#6F8295",
    "ACCENT": "#F08A6C",
    "LOW": "#93A3FF",
}
CATEGORICAL_DARK = ["#5EC2CF", "#F08A6C", "#93A3FF", "#E58AC0", "#D9BE4E", "#C9D6E3"]
HERO_GRADIENT = (DARK, PRIMARY)  # faixa da Home: texto branco nos dois modos

FONT_FAMILY = '"Source Sans Pro", "Source Sans 3", "Segoe UI", Roboto, Helvetica, Arial, sans-serif'


# ------------------------------------------------------- cor e contraste ----
def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


SEQUENTIAL = [_mix(SEQ_START, SEQ_END, i / 5) for i in range(6)]


def _lin(c: float) -> float:
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(h: str) -> float:
    r, g, b = (_lin(x) for x in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# Machado, Oliveira & Fernandes (2009), severidade 1,0, em RGB linear.
_CVD = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}


def _lab(v: tuple[float, float, float]) -> tuple[float, float, float]:
    x = 0.4124 * v[0] + 0.3576 * v[1] + 0.1805 * v[2]
    y = 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    z = 0.0193 * v[0] + 0.1192 * v[1] + 0.9505 * v[2]

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def simulate(h: str, kind: str | None) -> tuple[float, float, float]:
    v = tuple(_lin(x) for x in _rgb(h))
    if kind is None:
        return v  # type: ignore[return-value]
    m = _CVD[kind]
    return tuple(min(1.0, max(0.0, sum(m[i][j] * v[j] for j in range(3)))) for i in range(3))  # type: ignore[return-value]


def min_delta_e(palette: list[str], kind: str | None = None) -> float:
    """Menor distância CIE76 entre pares da paleta, na visão normal ou simulada."""
    labs = [_lab(simulate(c, kind)) for c in palette]
    return min(math.dist(a, b) for a, b in itertools.combinations(labs, 2))


def contrast_report() -> list[dict]:
    """Pares (texto/elemento × fundo) do painel e dos gráficos, com o mínimo exigido."""
    d = DARK_MODE
    pairs = [
        ("Texto", INK, PAGE_BG, 4.5),
        ("Texto", INK, CARD_BG, 4.5),
        ("Texto", INK, SIDEBAR_BG, 4.5),
        ("Texto secundário", MUTED, PAGE_BG, 4.5),
        ("Texto secundário", MUTED, CARD_BG, 4.5),
        ("Texto secundário", MUTED, SIDEBAR_BG, 4.5),
        ("Títulos", DARK, PAGE_BG, 4.5),
        ("Primária (links, ícones)", PRIMARY, PAGE_BG, 4.5),
        ("Primária (links, ícones)", PRIMARY, CARD_BG, 4.5),
        ("Branco sobre primária (botões, hero)", "#FFFFFF", PRIMARY, 4.5),
        ("Branco sobre escura (hero)", "#FFFFFF", DARK, 4.5),
        ("Selo forte (texto escuro)", DARK, FORTE, 4.5),
        ("Selo moderado (texto escuro)", DARK, MODERADO, 4.5),
        ("Selo fraco (texto escuro)", DARK, FRACO, 4.5),
        ("Marca 'acima/mais caro'", ACCENT, CARD_BG, 3.0),
        ("Marca 'abaixo/mais barato'", LOW, CARD_BG, 3.0),
        ("Escuro: texto", d["INK"], d["PAGE_BG"], 4.5),
        ("Escuro: texto", d["INK"], d["CARD_BG"], 4.5),
        ("Escuro: texto secundário", d["MUTED"], d["PAGE_BG"], 4.5),
        ("Escuro: texto secundário", d["MUTED"], d["CARD_BG"], 4.5),
        ("Escuro: primária", d["PRIMARY"], d["PAGE_BG"], 4.5),
        ("Escuro: primária", d["PRIMARY"], d["CARD_BG"], 4.5),
    ]
    pairs += [("Categórica (elemento gráfico)", c, PAGE_BG, 3.0) for c in CATEGORICAL]
    pairs += [("Categórica (elemento gráfico)", c, CARD_BG, 3.0) for c in CATEGORICAL]
    pairs += [("Escuro: categórica", c, d["CARD_BG"], 3.0) for c in CATEGORICAL_DARK]
    return [
        {"uso": u, "cor": f, "fundo": b, "razao": round(contrast_ratio(f, b), 2), "minimo": m}
        for u, f, b, m in pairs
    ]


# ------------------------------------------------------------------ Plotly ----
def plotly_template(dark: bool = False) -> dict:
    """Template "raiox": paleta, fundo transparente, grade suave, números pt-BR."""
    ink = DARK_MODE["INK"] if dark else INK
    muted = DARK_MODE["MUTED"] if dark else MUTED
    grid = DARK_MODE["GRID"] if dark else GRID
    card = DARK_MODE["CARD_BG"] if dark else CARD_BG
    axis = {
        "gridcolor": grid,
        "zerolinecolor": grid,
        "linecolor": grid,
        "tickcolor": grid,
        "tickfont": {"color": muted},
        "title": {"font": {"color": muted, "size": 13}},
        "automargin": True,
    }
    return {
        "layout": {
            "font": {"family": FONT_FAMILY, "color": ink, "size": 13},
            "title": {
                "font": {"color": ink, "size": 16},
                "x": 0,
                "xanchor": "left",
                "pad": {"l": 14},
            },
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "colorway": CATEGORICAL_DARK if dark else CATEGORICAL,
            "separators": ",.",  # vírgula decimal, ponto de milhar
            "xaxis": axis,
            "yaxis": axis,
            "legend": {"font": {"color": ink}, "bgcolor": "rgba(0,0,0,0)"},
            "hoverlabel": {
                "font": {"family": FONT_FAMILY, "color": ink},
                "bgcolor": card,
                "bordercolor": grid,
            },
            "geo": {"bgcolor": "rgba(0,0,0,0)"},
            "coloraxis": {"colorbar": {"tickfont": {"color": muted}}},
        }
    }


def register_plotly_templates() -> None:
    import plotly.graph_objects as go
    import plotly.io as pio

    pio.templates["raiox"] = go.layout.Template(plotly_template(dark=False))
    pio.templates["raiox_dark"] = go.layout.Template(plotly_template(dark=True))
    pio.templates.default = "raiox"


def plotly_layout(**overrides) -> dict:
    """Ajustes por gráfico sobre o template "raiox" (margens, altura, título)."""
    base = {"template": "raiox", "margin": {"l": 18, "r": 22, "t": 56, "b": 18}}
    base.update(overrides)
    return base


# -------------------------------------------------------------- matplotlib ----
def mpl_rc() -> dict:
    from cycler import cycler

    return {
        "font.family": "DejaVu Sans",
        "font.size": 15,
        "text.color": INK,
        "axes.edgecolor": BORDER,
        "axes.labelcolor": INK,
        "axes.titlecolor": DARK,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 1.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.prop_cycle": cycler(color=CATEGORICAL),
        "figure.facecolor": PAGE_BG,
        "axes.facecolor": PAGE_BG,
        "savefig.facecolor": PAGE_BG,
    }


# Compatibilidade com nomes antigos.
BG = CARD_BG
SURFACE = PAGE_BG
