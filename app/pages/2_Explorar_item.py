"""Explorar item: distribuição de preços, série real, fornecedores/marcas e compras individuais."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as c  # noqa: E402

c.setup_page("Explorar item")
f = c.filters()
st.title("Explorar item")
if not f:
    st.stop()

df = c.filtered_purchases(f, item=True)
p0, p1 = f["periodo"]
st.markdown(f"**{f['item_label']}** · {c.fmt.month(p0)} a {c.fmt.month(p1)}")
if df.height == 0:
    st.info("Sem compras deste item no período escolhido.")
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Compras", c.fmt.num(df["id_compra"].n_unique()))
k2.metric("Mediana", c.fmt.brl(df["preco_real"].median()))
k3.metric(
    "P10 – P90",
    f"{c.fmt.brl(df['preco_real'].quantile(0.1), 0)} – {c.fmt.brl(df['preco_real'].quantile(0.9), 0)}",
)
k4.metric("Órgãos compradores", c.fmt.num(df["codigo_uasg"].n_unique()))

# ----------------------------------------------------------- histograma ----
counts, edges = c.log_hist(df["preco_real"].to_numpy())
mids = (edges[:-1] * edges[1:]) ** 0.5
hist = go.Figure(
    go.Bar(
        x=mids,
        y=counts,
        width=(edges[1:] - edges[:-1]),
        marker_color=c.theme.PRIMARY,
        hovertemplate="R$ %{x:,.0f}<br>%{y} registros<extra></extra>",
    )
)
hist.update_xaxes(type="log", title="R$ por unidade (escala log)", tickformat=",.0f")
hist.update_yaxes(title="Registros")
hist.update_layout(**c.theme.plotly_layout(height=360, title="Distribuição de preços", bargap=0.05))
st.plotly_chart(hist, config={"displayModeBar": False})

# ----------------------------------------------------------------- série ----
serie = c.table("serie_item_mes").filter(
    (pl.col("codigo_catmat") == f["item"]) & pl.col("publicavel")
)
if serie.height:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=serie["mes"].to_list(),
            y=serie["mediana_real"].to_list(),
            mode="lines+markers",
            name=f"Real (R$ de {c.ref_month()})",
            line={"color": c.theme.PRIMARY, "width": 3},
            customdata=serie["n_registros"].to_list(),
            hovertemplate="%{x|%m/%Y}<br>R$ %{y:,.2f}<br>n = %{customdata}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=serie["mes"].to_list(),
            y=serie["mediana_nominal"].to_list(),
            mode="lines",
            name="Nominal",
            line={"color": c.theme.MUTED, "dash": "dot"},
        )
    )
    fig.update_layout(
        **c.theme.plotly_layout(
            height=380,
            title="Mediana mensal (histórico completo, sem outliers)",
            legend={"orientation": "h", "y": -0.2},
        )
    )
    fig.update_yaxes(title="R$ por unidade", tickformat=",.0f")
    st.plotly_chart(fig, config={"displayModeBar": False})
    st.caption(
        "Só meses com pelo menos 3 registros. Séries curtas e ruidosas: leia a tendência com cautela."
    )

# --------------------------------------------------- fornecedores / marcas ----
st.subheader("Fornecedores e marcas")
st.caption(
    "Participação no valor comprado (R$ reais) no período padrão da análise. Dado público, apresentado de forma agregada."
)
tipo = (
    st.segmented_control("Ver por", ["fornecedor", "marca"], default="fornecedor", key="exp_tipo")
    or "fornecedor"
)
forn = (
    c.table("fornecedores_item")
    .filter((pl.col("codigo_catmat") == f["item"]) & (pl.col("tipo") == tipo))
    .sort("rank")
)
if forn.height:
    top = forn.head(10).sort("participacao_valor")
    bar = go.Figure(
        go.Bar(
            x=top["participacao_valor"].to_list(),
            y=top["nome"].to_list(),
            orientation="h",
            marker_color=c.theme.PRIMARY,
            hovertemplate="%{y}<br>%{x:.1%}<extra></extra>",
        )
    )
    bar.update_xaxes(tickformat=".0%", title="Participação no valor")
    bar.update_layout(
        **c.theme.plotly_layout(
            height=max(260, 32 * top.height), title=f"Top {top.height} por valor"
        )
    )
    st.plotly_chart(bar, config={"displayModeBar": False})
    r0 = forn.row(0, named=True)
    st.caption(
        f"HHI = {c.fmt.num(r0['hhi'])} · {forn.height} {tipo}s · os 3 maiores somam {c.fmt.pct(r0['cr3'], 0)} do valor."
    )

# ------------------------------------------------------ compras individuais ----
st.subheader("Compras individuais")
tab = df.sort("data_compra", descending=True).select(
    pl.col("data_compra").alias("Data"),
    pl.col("uf").alias("UF"),
    pl.col("nome_uasg").alias("Órgão (UASG)"),
    pl.col("esfera").replace({"F": "Federal", "E": "Estadual", "M": "Municipal"}).alias("Esfera"),
    pl.col("fornecedor").alias("Fornecedor"),
    pl.col("marca").alias("Marca"),
    pl.col("quantidade_base").alias("Quantidade"),
    pl.col("preco_nominal").alias("Preço nominal (R$)"),
    pl.col("preco_real").alias("Preço real (R$)"),
    pl.col("outlier").alias("Outlier"),
    pl.col("link_registro").alias("Registro"),
)
st.dataframe(
    tab,
    hide_index=True,
    column_config={
        "Preço nominal (R$)": st.column_config.NumberColumn(format="localized"),
        "Preço real (R$)": st.column_config.NumberColumn(format="localized"),
        "Registro": st.column_config.LinkColumn("Registro", display_text="abrir"),
    },
)
st.caption(
    "“Registro” abre a consulta do item na API de Dados Abertos do Compras.gov.br (JSON). Fornecedores pessoa física aparecem anonimizados."
)
c.footer()
