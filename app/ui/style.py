"""Identidade visual do painel: CSS global (injetado uma vez por página por `apply`) e
componentes (hero, cards de KPI e de achado, selos, títulos de seção, rodapé).

As cores vêm de `raiox.viz.theme` (fonte única). O CSS acompanha o tema ativo do Streamlit
(claro/escuro) lendo `st.context.theme.type`.
"""

from __future__ import annotations

import html
import re
from functools import cache
from pathlib import Path

import streamlit as st

from raiox.viz import theme

ASSETS = Path(__file__).resolve().parents[1] / "assets"
LOGO = ASSETS / "logo.svg"

FAMILY_ICONS = [
    (r"marca-passo", "marca_passo"),
    (r"v[aá]lvula", "valvula"),
    (r"placa|parafuso|haste", "placa_parafuso"),
    (r"quadril|joelho|articular", "quadril_joelho"),
    (r"stent|endopr|cateter|vascular", "stent"),
]


def is_dark() -> bool:
    try:
        return (st.context.theme.type or "light") == "dark"
    except Exception:  # noqa: BLE001 — fora de uma sessão (testes) ou versão sem st.context.theme
        return False


def tokens(dark: bool) -> dict[str, str]:
    if dark:
        d = theme.DARK_MODE
        return {
            "page": d["PAGE_BG"],
            "card": d["CARD_BG"],
            "sidebar": d["SIDEBAR_BG"],
            "primary": d["PRIMARY"],
            "dark": d["DARK"],
            "ink": d["INK"],
            "muted": d["MUTED"],
            "border": d["BORDER"],
            "shadow": "0 1px 2px rgba(0,0,0,.35), 0 6px 18px rgba(0,0,0,.25)",
            "hover": "rgba(94,194,207,.12)",
        }
    return {
        "page": theme.PAGE_BG,
        "card": theme.CARD_BG,
        "sidebar": theme.SIDEBAR_BG,
        "primary": theme.PRIMARY,
        "dark": theme.DARK,
        "ink": theme.INK,
        "muted": theme.MUTED,
        "border": theme.BORDER,
        "shadow": "0 1px 2px rgba(18,48,74,.06), 0 6px 18px rgba(18,48,74,.07)",
        "hover": "rgba(14,110,126,.08)",
    }


CSS = """
:root {{
  --rx-page: {page}; --rx-card: {card}; --rx-sidebar: {sidebar}; --rx-primary: {primary};
  --rx-dark: {dark}; --rx-ink: {ink}; --rx-muted: {muted}; --rx-border: {border};
  --rx-shadow: {shadow}; --rx-hover: {hover};
  --rx-forte: {forte}; --rx-moderado: {moderado}; --rx-fraco: {fraco}; --rx-badge-ink: {badge_ink};
  --rx-hero-a: {hero_a}; --rx-hero-b: {hero_b};
}}
.stApp {{ background: var(--rx-page); }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stSidebar"] {{ background: var(--rx-sidebar); border-right: 1px solid var(--rx-border); }}
[data-testid="stMainBlockContainer"] {{ padding-top: 2.2rem; max-width: 1240px; }}
h1, h2, h3, h4 {{ color: var(--rx-dark); letter-spacing: -0.01em; }}
[data-testid="stHeading"] [data-testid="stIconMaterial"] {{ color: var(--rx-primary); }}

/* Títulos de seção: ícone + linha fina embaixo */
[data-testid="stMainBlockContainer"] [data-testid="stHeading"] h3 {{
  border-bottom: 1px solid var(--rx-border); padding-bottom: .45rem; margin-top: 1.2rem;
}}

/* Cards (containers com chave rx-card-*, rx-kpi-*, rx-panel-*) */
[class*="st-key-rx-card"], [class*="st-key-rx-kpi"], [class*="st-key-rx-panel"] {{
  background: var(--rx-card); border: 1px solid var(--rx-border); border-radius: 12px;
  box-shadow: var(--rx-shadow); padding: 1rem 1.15rem;
}}
[class*="st-key-rx-card"] {{ height: 100%; gap: .55rem; }}
[class*="st-key-rx-card-forte"] {{ border-left: 4px solid var(--rx-forte); }}
[class*="st-key-rx-card-moderado"] {{ border-left: 4px solid var(--rx-moderado); }}
[class*="st-key-rx-card-fraco"] {{ border-left: 4px solid var(--rx-fraco); }}
[class*="st-key-rx-card"] p {{ margin-bottom: .2rem; }}
[class*="st-key-rx-kpi"] {{ padding: .85rem 1rem .7rem; }}
[class*="st-key-rx-kpi"] [data-testid="stMetricLabel"] p {{ color: var(--rx-muted); font-weight: 600; }}
[class*="st-key-rx-kpi"] [data-testid="stMetricLabel"] [data-testid="stIconMaterial"] {{ color: var(--rx-primary); }}
[class*="st-key-rx-kpi"] [data-testid="stMetricValue"],
[class*="st-key-rx-kpi"] [data-testid="stMetricValue"] p {{
  color: var(--rx-dark); font-weight: 700; font-size: clamp(1.3rem, 1.9vw, 1.9rem) !important;
  line-height: 1.2;
}}
[class*="st-key-rx-kpi"] [data-testid="stMetricValue"] .stMarkdownEllipsis,
[class*="st-key-rx-kpi"] [data-testid="stMetricValue"] p {{
  white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
}}

/* Selo de robustez */
.rx-badge-row {{
  display: flex; align-items: center; justify-content: space-between; gap: .5rem; margin-bottom: .4rem;
}}
.rx-badge {{
  display: inline-flex; align-items: center; font-size: .74rem; font-weight: 700;
  letter-spacing: .04em; text-transform: uppercase; padding: .16rem .6rem; border-radius: 999px;
  color: var(--rx-badge-ink);
}}
.rx-badge.forte {{ background: var(--rx-forte); }}
.rx-badge.moderado {{ background: var(--rx-moderado); }}
.rx-badge.fraco, .rx-badge.sem_comparacao {{ background: var(--rx-fraco); }}
.rx-fam {{ color: var(--rx-primary); display: inline-flex; width: 22px; height: 22px; }}
.rx-fam svg {{ width: 22px; height: 22px; }}

/* Expanders, tabelas, abas e gráficos com o mesmo acabamento dos cards */
[data-testid="stExpander"] details {{
  background: var(--rx-card); border: 1px solid var(--rx-border); border-radius: 12px;
  box-shadow: var(--rx-shadow);
}}
[data-testid="stExpander"] summary:hover {{ color: var(--rx-primary); }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{
  border: 1px solid var(--rx-border); border-radius: 12px; overflow: hidden;
  box-shadow: var(--rx-shadow); background: var(--rx-card);
}}
[data-testid="stTabs"] [data-baseweb="tab-list"] {{ gap: .3rem; border-bottom: 1px solid var(--rx-border); }}
[data-testid="stTabs"] [data-baseweb="tab"] {{
  background: var(--rx-card); border: 1px solid var(--rx-border); border-bottom: none;
  border-radius: 10px 10px 0 0; padding: .35rem .9rem;
}}
[data-testid="stPlotlyChart"] {{
  background: var(--rx-card); border: 1px solid var(--rx-border); border-radius: 12px;
  box-shadow: var(--rx-shadow); overflow: hidden;
}}
[data-testid="stAlert"] {{ border-radius: 12px; }}

/* Navegação lateral */
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{ border-radius: 8px; }}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{ background: var(--rx-hover); }}
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] {{ color: var(--rx-primary); }}

/* Hero da página inicial */
.rx-hero {{
  display: flex; align-items: center; justify-content: space-between; gap: 1.5rem;
  background: linear-gradient(120deg, var(--rx-hero-a) 0%, var(--rx-hero-b) 100%);
  border-radius: 16px; padding: 1.9rem 2.1rem; margin: 0 0 1.3rem; overflow: hidden;
  box-shadow: var(--rx-shadow);
}}
.rx-hero .rx-text {{ flex: 1 1 52%; min-width: 0; }}
.rx-hero .rx-kicker {{
  text-transform: uppercase; letter-spacing: .14em; font-size: .78rem; font-weight: 700; color: #CDEDF1;
}}
.rx-hero h1 {{ color: #FFFFFF; font-size: 2.5rem; line-height: 1.1; margin: .35rem 0 0; padding: 0; }}
.rx-hero p {{ color: #EAF6F8; font-size: 1.1rem; line-height: 1.45; margin: .7rem 0 0; max-width: 46ch; }}
.rx-hero .rx-art {{ flex: 0 1 42%; max-width: 440px; }}
.rx-hero .rx-art svg {{ width: 100%; height: auto; display: block; }}
@media (max-width: 820px) {{
  [data-testid="stMainBlockContainer"] {{ padding-top: 4rem; }}
  .rx-hero .rx-art {{ display: none; }}
  .rx-hero {{ padding: 1.4rem 1.25rem; }}
  .rx-hero h1 {{ font-size: 1.9rem; }}
  .rx-hero p {{ font-size: 1rem; }}
}}

/* Rodapé */
.rx-footer {{
  margin-top: 2.6rem; padding-top: .9rem; border-top: 1px solid var(--rx-border);
  color: var(--rx-muted); font-size: .84rem; line-height: 1.55;
}}
.rx-footer a {{ color: var(--rx-primary); text-decoration: none; font-weight: 600; }}
.rx-footer a:hover {{ text-decoration: underline; }}
.rx-footer .rx-links {{ margin-top: .35rem; display: flex; flex-wrap: wrap; gap: .4rem 1.2rem; }}
"""


@cache
def _css(dark: bool) -> str:
    t = tokens(dark)
    return CSS.format(
        **t,
        forte=theme.FORTE,
        moderado=theme.MODERADO,
        fraco=theme.FRACO,
        badge_ink=theme.DARK,
        hero_a=theme.HERO_GRADIENT[0],
        hero_b=theme.HERO_GRADIENT[1],
    )


def apply() -> None:
    """Injeta o CSS global (uma chamada por página, via setup_page)."""
    st.html(f"<style>{_css(is_dark())}</style>")


@cache
def _svg(name: str) -> str:
    """SVG em uma linha só (o Markdown trata linhas indentadas como bloco de código)."""
    text = (ASSETS / name).read_text(encoding="utf-8")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def family_icon(familia: str | None) -> str:
    low = (familia or "").lower()
    for pattern, name in FAMILY_ICONS:
        if re.search(pattern, low):
            return f'<span class="rx-fam" title="{html.escape(familia or "")}">{_svg(f"icons/{name}.svg")}</span>'
    return ""


def hero(title: str, subtitle: str, kicker: str = "Painel de dados abertos") -> None:
    st.markdown(
        '<div class="rx-hero"><div class="rx-text">'
        f'<div class="rx-kicker">{html.escape(kicker)}</div>'
        f"<h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>"
        f'<div class="rx-art" aria-hidden="true">{_svg("hero.svg")}</div></div>',
        unsafe_allow_html=True,
    )


def kpis(items: list[tuple[str, str, str, str | None]]) -> None:
    """Linha de KPIs em cards: (ícone material, rótulo, valor, ajuda)."""
    cols = st.columns(len(items))
    for i, (col, (icon, label, value, help_)) in enumerate(zip(cols, items, strict=True)):
        with col, st.container(key=f"rx-kpi-{i}"):
            st.metric(f":material/{icon}: {label}", value, help=help_)


def badge(robustez: str) -> str:
    label = {"sem_comparacao": "sem comparação"}.get(robustez, robustez)
    return f'<span class="rx-badge {html.escape(robustez)}">{html.escape(label)}</span>'


def finding_card(r: dict, key: str) -> None:
    """Card de achado: selo de robustez, ícone da família, título, frase e base."""
    with st.container(key=f"rx-card-{r['robustez']}-{key}"):
        st.markdown(
            f'<div class="rx-badge-row">{badge(r["robustez"])}{family_icon(r.get("familia"))}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f"**{r['titulo']}**")
        st.write(r["frase"])
        st.caption(f"n: {r['n_descricao']} · Período: {r['periodo']} · Fonte: {r['fonte']}")


def page_title(title: str, icon: str) -> None:
    st.title(f":material/{icon}: {title}")


def section(title: str, icon: str) -> None:
    st.subheader(f":material/{icon}: {title}")


def footer(ref_month: str, repo_url: str, linkedin: str, sources: str) -> None:
    st.markdown(
        '<div class="rx-footer">'
        f"<div>Fonte: {html.escape(sources)}. Elaboração: <strong>Gabriel Cunha</strong>. "
        f"Valores em R$ de {html.escape(ref_month)}, deflacionados pelo IPCA. Diferenças de preço têm "
        "muitas causas legítimas (volume, prazo, logística, consignação, especificação).</div>"
        '<div class="rx-links">'
        f'<a href="{html.escape(linkedin)}" target="_blank" rel="noopener">LinkedIn de Gabriel Cunha</a>'
        f'<a href="{html.escape(repo_url)}" target="_blank" rel="noopener">Código e dados no GitHub</a>'
        "</div></div>",
        unsafe_allow_html=True,
    )
