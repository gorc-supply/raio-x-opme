"""Preços por UF: mapa, distribuição por UF e tabela para download."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as c  # noqa: E402

c.setup_page("Preços por UF")
f = c.filters()
c.page_title("Preços por UF", "map")
if not f:
    st.stop()

df = c.filtered_purchases(f, item=True)
p0, p1 = f["periodo"]
st.markdown(
    f"**{f['item_label']}** · {c.fmt.month(p0)} a {c.fmt.month(p1)} · R$ de {c.ref_month()} por unidade"
)
if df.height == 0:
    st.info("Sem compras deste item no período escolhido.")
    st.stop()

stats = c.uf_stats(df)
elig = stats.filter(pl.col("amostra_suficiente"))
insuf = stats.filter(~pl.col("amostra_suficiente"))
regras = c.meta().get("regras", {})

# ------------------------------------------------------------------- mapa ----
geo = c.geojson()
all_ufs = c.ufs()["uf"].to_list()
fig = go.Figure()
no_data = [u for u in all_ufs if u not in stats["uf"].to_list()]
gray_ufs = insuf["uf"].to_list() + no_data
if gray_ufs:
    hover = []
    for u in gray_ufs:
        r = insuf.filter(pl.col("uf") == u)
        hover.append(
            f"<b>{u}</b><br>Amostra insuficiente: {r['n_compras'][0]} compras, {r['n_orgaos'][0]} órgãos"
            if r.height
            else f"<b>{u}</b><br>Sem compras no período"
        )
    fig.add_trace(
        go.Choropleth(
            geojson=geo,
            featureidkey="properties.uf",
            locations=gray_ufs,
            z=[0] * len(gray_ufs),
            colorscale=[[0, c.theme.INSUFFICIENT], [1, c.theme.INSUFFICIENT]],
            showscale=False,
            marker_line_color="white",
            hovertext=hover,
            hoverinfo="text",
            name="Amostra insuficiente ou sem compras (fora do ranking)",
            showlegend=True,
        )
    )
if elig.height:
    fig.add_trace(
        go.Choropleth(
            geojson=geo,
            featureidkey="properties.uf",
            locations=elig["uf"].to_list(),
            z=elig["mediana"].to_list(),
            colorscale=[
                [i / (len(c.theme.SEQUENTIAL) - 1), col] for i, col in enumerate(c.theme.SEQUENTIAL)
            ],
            marker_line_color=c.theme.DARK,  # contorno escuro: UF elegível ≠ cinza "insuficiente"
            colorbar={
                "title": {"text": "Mediana (R$ por unidade)", "side": "top"},
                "tickformat": ",.0f",
                "orientation": "h",
                "x": 0.5,
                "xanchor": "center",
                "y": -0.04,
                "yanchor": "top",
                "len": 0.8,
                "thickness": 12,
            },
            marker_line_width=1.4,
            hovertext=[
                f"<b>{r['uf']}</b><br>Mediana: {c.fmt.brl(r['mediana'])}<br>{r['n_compras']} compras · {r['n_orgaos']} órgãos"
                for r in elig.iter_rows(named=True)
            ],
            hoverinfo="text",
            name="Mediana",
        )
    )
fig.update_geos(fitbounds="locations", visible=False)
fig.update_layout(
    **c.theme.plotly_layout(
        height=540,
        title="Mediana do preço por UF",
        legend={"orientation": "h", "y": 1.0, "x": 0, "yanchor": "bottom", "itemclick": False},
        margin={"l": 8, "r": 8, "t": 84, "b": 70},
    )
)
c.plot(fig)
st.caption(
    f"UFs em cinza (legenda acima do mapa): amostra insuficiente (menos de {regras.get('min_compras_uf', 5)} compras ou menos de "
    f"{regras.get('min_orgaos_uf', 2)} órgãos compradores) ou sem compras — não entram em ranking."
)

# --------------------------------------------------------------- boxplot ----
if elig.height:
    order = elig.sort("mediana", descending=True)["uf"].to_list()
    box = go.Figure()
    for u in order:
        vals = df.filter(pl.col("uf") == u)["preco_real"].to_list()
        box.add_trace(
            go.Box(
                y=vals,
                name=u,
                boxpoints="all",
                jitter=0.4,
                pointpos=0,
                marker={"size": 4, "color": c.theme.PRIMARY},
                line={"color": c.theme.PRIMARY},
                showlegend=False,
            )
        )
    spread = df["preco_real"].quantile(0.9) / max(df["preco_real"].quantile(0.1), 1e-9)
    box.update_layout(
        **c.theme.plotly_layout(height=420, title="Distribuição por UF (amostra suficiente)")
    )
    box.update_yaxes(
        title="R$ por unidade",
        type="log" if spread > 5 else "linear",
        tickformat=",.0f",
        dtick="D2" if spread > 5 else None,
    )
    c.plot(box)

# ------------------------------------------------- robustez da comparação ----
disp = c.table("dispersao_item").filter(pl.col("codigo_catmat") == f["item"])
m = c.meta()
if (
    disp.height
    and m
    and (str(p0), str(p1)) == (m["periodo_inicio"], m["periodo_fim"])
    and not f["com_outliers"]
):
    r = disp.row(0, named=True)
    with st.container(key="rx-panel-comparacao"):
        st.markdown("**:material/balance: Comparação entre UFs (regras da metodologia)**")
        if r["robustez"] == "sem_comparacao":
            st.write(f"Sem comparação: {r['motivo_robustez']}.")
        else:
            st.write(
                f"Maior mediana: **{r['uf_max']}** ({c.fmt.brl(r['mediana_max'])}, {r['n_compras_max']} compras). "
                f"Menor: **{r['uf_min']}** ({c.fmt.brl(r['mediana_min'])}, {r['n_compras_min']} compras). "
                f"Razão {c.fmt.ratio(r['razao'])} (IC 95%: {c.fmt.ratio(r['ic_inf'])} a {c.fmt.ratio(r['ic_sup'])})."
            )
            st.write(f"Robustez: **{r['robustez']}** — {r['motivo_robustez']}.")
else:
    st.caption(
        "A razão com intervalo de confiança é calculada para o período padrão, sem outliers."
    )

# ---------------------------------------------------------------- tabela ----
show = stats.select(
    pl.col("uf").alias("UF"),
    pl.col("nome").alias("Estado"),
    pl.col("n_compras").alias("Compras"),
    pl.col("n_orgaos").alias("Órgãos"),
    pl.col("mediana").round(2).alias("Mediana (R$)"),
    pl.col("p10").round(2).alias("P10 (R$)"),
    pl.col("p90").round(2).alias("P90 (R$)"),
    pl.col("amostra_suficiente").alias("Amostra suficiente"),
)
st.dataframe(
    show,
    hide_index=True,
    column_config={
        k: st.column_config.NumberColumn(k, format="localized")
        for k in ("Mediana (R$)", "P10 (R$)", "P90 (R$)")
    },
)
st.download_button(
    "Baixar tabela (CSV)",
    show.write_csv(separator=";").encode("utf-8-sig"),
    file_name=f"precos_uf_{f['item']}.csv",
    mime="text/csv",
)
c.footer()
