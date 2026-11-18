"""Funções compartilhadas pelo painel. O painel NUNCA chama API: lê só data/gold e data/reference."""

from __future__ import annotations

import contextlib
import json
import os
import sys
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from raiox import fmt  # noqa: E402
from raiox.viz import theme  # noqa: E402

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
from ui import style as ui  # noqa: E402

theme.register_plotly_templates()

GOLD = Path(os.environ.get("RAIOX_GOLD_DIR", ROOT / "data" / "gold"))
REF = ROOT / "data" / "reference"
DOCS = ROOT / "docs"

LINKEDIN = "https://www.linkedin.com/in/gabriel-cunha-xp"


# ------------------------------------------------------------------ dados ----
@st.cache_data(show_spinner=False)
def table(name: str) -> pl.DataFrame:
    path = GOLD / f"{name}.parquet"
    return pl.read_parquet(path) if path.exists() else pl.DataFrame()


@st.cache_data(show_spinner=False)
def meta() -> dict:
    path = GOLD / "meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


@st.cache_data(show_spinner=False)
def geojson() -> dict:
    return json.loads((REF / "uf.geojson").read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def ufs() -> pl.DataFrame:
    return pl.read_csv(REF / "ufs.csv")


@st.cache_data(show_spinner=False)
def doc(name: str) -> str:
    path = DOCS / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


@st.cache_data(show_spinner=False)
def settings_info() -> dict:
    import yaml

    data = yaml.safe_load((ROOT / "config" / "settings.yaml").read_text(encoding="utf-8"))
    return {
        "repo_url": data["project"]["repo_url"],
        "dashboard_url": data["project"]["dashboard_url"],
        "footer": data["charts"]["footer"],
    }


def ref_month() -> str:
    m = meta()
    return fmt.month(date.fromisoformat(m["mes_ref_deflacao"])) if m else "—"


SOURCES = (
    "Compras.gov.br (API de Dados Abertos), ComexStat/MDIC, BCB, IBGE, ANVISA e SIGTAP/DATASUS"
)


def footer() -> None:
    ui.footer(ref_month(), settings_info()["repo_url"], LINKEDIN, SOURCES)


def plot(fig) -> None:
    """Desenha um gráfico Plotly com o template do projeto (claro ou escuro, conforme o tema)."""
    if ui.is_dark():
        fig.update_layout(template="raiox_dark")
    st.plotly_chart(fig, theme=None, config={"displayModeBar": False, "locale": "pt-BR"})


# ---------------------------------------------------------------- filtros ----
def _default_item() -> int | None:
    """Item inicial: o que tem mais UFs com amostra suficiente (melhor para o mapa)."""
    d = table("dispersao_item")
    if d.height == 0:
        return None
    return int(d.sort(["n_ufs_elegiveis", "n_compras_total"], descending=True)["codigo_catmat"][0])


def _months(start: date, end: date) -> list[date]:
    out, cur = [], date(start.year, start.month, 1)
    while cur <= end:
        out.append(cur)
        cur = date(cur.year + (cur.month // 12), cur.month % 12 + 1, 1)
    return out


NAV = [
    ("Home.py", "Início", ":material/home:"),
    ("pages/1_Precos_por_UF.py", "Preços por UF", ":material/map:"),
    ("pages/2_Explorar_item.py", "Explorar item", ":material/search:"),
    ("pages/3_Importacao.py", "Importação", ":material/public:"),
    ("pages/4_Tabela_SUS.py", "Tabela SUS × preço", ":material/receipt_long:"),
    ("pages/5_Metodologia.py", "Metodologia", ":material/menu_book:"),
    ("pages/6_Sobre.py", "Sobre", ":material/person:"),
]
FILTER_KEYS = ("f_familia", "f_item", "f_periodo", "f_outliers")


def sidebar_nav() -> None:
    """Navegação com rótulos acentuados (a navegação automática usa o nome do arquivo)."""
    with st.sidebar:
        for path, label, icon in NAV:
            try:
                st.page_link(path, label=label, icon=icon)
            except Exception:  # noqa: BLE001 — página rodando isolada (fora do Home.py)
                continue
        st.divider()


def sidebar_filters() -> dict:
    """Filtros globais (família, item, período, outliers) na barra lateral.

    Os valores persistem entre páginas: o Streamlit descarta o estado de widgets que não
    aparecem numa execução; reatribuir a chave no início de cada página mantém o valor.
    """
    for k in FILTER_KEYS:
        if k in st.session_state:
            st.session_state[k] = st.session_state[k]
    comp = table("compras_detalhe")
    m = meta()
    with st.sidebar:
        st.subheader(":material/tune: Filtros")
        if comp.height == 0:
            st.warning("Sem dados na gold. Rode `uv run raiox all`.")
            return {}
        fams = sorted(comp["familia"].unique().to_list())
        familia = st.selectbox("Família", ["Todas", *fams], key="f_familia")
        items = (
            (comp.filter(pl.col("familia") == familia) if familia != "Todas" else comp)
            .select("codigo_catmat", "nome_curto")
            .unique()
            .sort("nome_curto")
        )
        labels = {
            r["codigo_catmat"]: f"{r['nome_curto']} ({r['codigo_catmat']})"
            for r in items.iter_rows(named=True)
        }
        codes = list(labels)
        default_code = st.session_state.get("f_item", _default_item())
        idx = codes.index(default_code) if default_code in codes else 0
        item = st.selectbox(
            "Item (CATMAT)", codes, index=idx, format_func=lambda c: labels[c], key="f_item"
        )
        months = _months(comp["mes"].min(), comp["mes"].max())
        p0 = date.fromisoformat(m["periodo_inicio"]) if m else months[0]
        p1 = date.fromisoformat(m["periodo_fim"]) if m else months[-1]
        periodo = st.select_slider(
            "Período (mês da compra)",
            options=months,
            value=(max(p0, months[0]), min(p1, months[-1])),
            format_func=fmt.month,
            key="f_periodo",
        )
        com_outliers = st.toggle(
            "Incluir outliers",
            value=False,
            key="f_outliers",
            help="Outliers são marcados por IQR (3× em log) e MAD; o padrão é excluí-los.",
        )
        st.caption(
            f"Período padrão da análise: {m.get('periodo_label', '—')}. Valores em R$ de {ref_month()}."
        )
    return {
        "familia": familia,
        "item": item,
        "periodo": periodo,
        "com_outliers": com_outliers,
        "item_label": labels.get(item, str(item)),
    }


def filters() -> dict:
    """Desenha a navegação e os filtros globais e devolve os valores escolhidos."""
    sidebar_nav()
    return sidebar_filters()


def filtered_purchases(f: dict, item: bool = True) -> pl.DataFrame:
    comp = table("compras_detalhe")
    if comp.height == 0 or not f:
        return comp
    p0, p1 = f["periodo"]
    out = comp.filter(pl.col("mes").is_between(p0, p1))
    if not f["com_outliers"]:
        out = out.filter(~pl.col("outlier"))
    if item:
        out = out.filter(pl.col("codigo_catmat") == f["item"])
    elif f["familia"] != "Todas":
        out = out.filter(pl.col("familia") == f["familia"])
    return out


def uf_stats(df: pl.DataFrame) -> pl.DataFrame:
    """Estatística por UF com a mesma regra de elegibilidade do pipeline (meta.json)."""
    regras = meta().get("regras", {"min_compras_uf": 5, "min_orgaos_uf": 2})
    if df.height == 0:
        return pl.DataFrame()
    out = (
        df.group_by("uf", maintain_order=True)
        .agg(
            pl.col("id_compra").n_unique().alias("n_compras"),
            pl.col("codigo_uasg").n_unique().alias("n_orgaos"),
            pl.len().alias("n_registros"),
            pl.col("preco_real").median().alias("mediana"),
            pl.col("preco_real").quantile(0.10, "linear").alias("p10"),
            pl.col("preco_real").quantile(0.90, "linear").alias("p90"),
            pl.col("quantidade_base").sum().alias("quantidade"),
        )
        .with_columns(
            (
                (pl.col("n_compras") >= regras["min_compras_uf"])
                & (pl.col("n_orgaos") >= regras["min_orgaos_uf"])
            ).alias("amostra_suficiente")
        )
        .join(ufs().select("uf", "nome", "regiao"), on="uf", how="left")
        .sort("mediana", descending=True)
    )
    return out


def wrap_label(text: str, width: int = 28) -> str:
    """Quebra rótulos longos de eixo em linhas (Plotly usa <br>), para caber no celular."""
    import textwrap

    return "<br>".join(textwrap.wrap(str(text), width)) or str(text)


def log_hist(values: np.ndarray, bins: int = 30) -> tuple[np.ndarray, np.ndarray]:
    v = values[values > 0]
    edges = np.logspace(np.log10(v.min()), np.log10(v.max()) + 1e-9, bins + 1)
    counts, _ = np.histogram(v, bins=edges)
    return counts, edges


page_title = ui.page_title
section = ui.section


def setup_page(title: str) -> None:
    """Configuração comum a todas as páginas: título da aba, ícone, logo e CSS global."""
    with contextlib.suppress(st.errors.StreamlitAPIException):  # já configurado
        st.set_page_config(
            page_title=f"{title} · Raio-X OPME", page_icon=str(ui.LOGO), layout="wide"
        )
    st.logo(str(ui.LOGO), size="large", link=settings_info()["dashboard_url"])
    ui.apply()


__all__ = ["fmt", "theme", "ui"]
