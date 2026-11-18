"""Importação: valores ao longo do tempo, origens, concentração e a ponte com o preço público."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as c  # noqa: E402

c.setup_page("Importação")
c.filters()
c.page_title("Importação e dependência externa", "public")
imp = c.table("importacao_ncm_ano")
if imp.height == 0:
    st.info("Sem dados de comércio exterior na gold.")
    st.stop()

fams = sorted(imp["familia_macro"].drop_nulls().unique().to_list())
default = [
    x
    for x in ("Stents", "Próteses articulares", "Placas, parafusos e hastes", "Marca-passos")
    if x in fams
]
sel = st.multiselect("Famílias (NCM)", fams, default=default or fams[:3], key="imp_fams")
metric = st.segmented_control("Valor", ["FOB", "CIF"], default="FOB", key="imp_metric") or "FOB"
col = "fob_usd" if metric == "FOB" else "cif_usd"

# ------------------------------------------------------------ série anual ----
agg = (
    imp.filter(pl.col("familia_macro").is_in(sel))
    .group_by("familia_macro", "ano", maintain_order=True)
    .agg(pl.col(col).sum(), pl.col("export_fob_usd").sum(), pl.col("meses_com_dados").max())
    .sort("ano")
)
fig = go.Figure()
for i, fam in enumerate(sel):
    g = agg.filter(pl.col("familia_macro") == fam)
    fig.add_trace(
        go.Scatter(
            x=g["ano"].to_list(),
            y=(g[col] / 1e6).to_list(),
            mode="lines+markers",
            name=fam,
            line={"width": 3, "color": c.theme.CATEGORICAL[i % len(c.theme.CATEGORICAL)]},
            hovertemplate="%{x}: US$ %{y:,.1f} mi<extra>" + fam + "</extra>",
        )
    )
last_year = int(imp["ano"].max())
partial = imp.filter(pl.col("ano") == last_year)["meses_com_dados"].max()
fig.update_layout(
    **c.theme.plotly_layout(
        height=420,
        title=f"Importação anual ({metric}, US$ milhões)",
        legend={"orientation": "h", "y": -0.2},
    )
)
fig.update_yaxes(title="US$ milhões", tickformat=",.0f")
c.plot(fig)
st.caption(
    f"{last_year} é parcial ({partial} meses). Stents mudaram de NCM em 2020 (9021.90.81 → 9021.90.12); a série soma os dois códigos."
)

# --------------------------------------------------- balança por família ----
full = imp.filter((pl.col("meses_com_dados") == 12) & ~pl.col("ncm_historico"))
yr = int(full["ano"].max()) if full.height else last_year
bal = (
    full.filter(pl.col("ano") == yr)
    .group_by("familia_macro", maintain_order=True)
    .agg(
        pl.col("fob_usd").sum().alias("Importação (US$ FOB)"),
        pl.col("export_fob_usd").sum().alias("Exportação (US$ FOB)"),
    )
    .with_columns(
        (pl.col("Exportação (US$ FOB)") / pl.col("Importação (US$ FOB)")).alias("Cobertura")
    )
    .sort("Importação (US$ FOB)", descending=True)
    .rename({"familia_macro": "Família"})
)
c.section(f"Balança comercial por família ({yr})", "balance")
st.dataframe(
    bal,
    hide_index=True,
    column_config={
        "Importação (US$ FOB)": st.column_config.NumberColumn(format="localized"),
        "Exportação (US$ FOB)": st.column_config.NumberColumn(format="localized"),
        "Cobertura": st.column_config.ProgressColumn(
            "Exportação ÷ importação", format="percent", min_value=0, max_value=1
        ),
    },
)

# ---------------------------------------------------------------- origens ----
c.section("Países de origem", "flag")
ori = c.table("importacao_origem")
ncm_opts = imp.filter(~pl.col("ncm_historico")).select("ncm", "descricao_ncm").unique().sort("ncm")
labels = {
    r["ncm"]: f"{r['ncm'][:4]}.{r['ncm'][4:6]}.{r['ncm'][6:]} — {r['descricao_ncm']}"
    for r in ncm_opts.iter_rows(named=True)
}
cc1, cc2 = st.columns([3, 1])
ncm = cc1.selectbox("NCM", list(labels), format_func=lambda x: labels[x], key="imp_ncm")
years = sorted(ori.filter(pl.col("ncm") == ncm)["ano"].unique().to_list(), reverse=True)
year = cc2.selectbox("Ano", years, index=1 if len(years) > 1 else 0, key="imp_ano")
o = (
    ori.filter((pl.col("ncm") == ncm) & (pl.col("ano") == year))
    .sort("rank")
    .head(10)
    .sort("participacao_fob")
)
row = imp.filter((pl.col("ncm") == ncm) & (pl.col("ano") == year))
if o.height:
    bar = go.Figure(
        go.Bar(
            x=o["participacao_fob"].to_list(),
            y=o["pais"].to_list(),
            orientation="h",
            marker_color=c.theme.PRIMARY,
            hovertemplate="%{y}: %{x:.1%}<extra></extra>",
        )
    )
    bar.update_xaxes(tickformat=".0%", title="Participação no FOB")
    bar.update_layout(
        **c.theme.plotly_layout(height=max(260, 30 * o.height), title=f"Top origens — {year}")
    )
    c.plot(bar)
if row.height:
    r = row.row(0, named=True)
    unit_txt = (
        f"Preço implícito: {c.fmt.usd_compact(r['preco_cif_usd_unid'])} CIF por unidade."
        if r["preco_cif_usd_unid"] is not None
        else f"Unidade estatística em kg: preço implícito de US$ {c.fmt.num(r['preco_cif_usd_kg'] or 0, 0)} CIF por kg (não comparável com preço por peça)."
    )
    st.caption(
        f"HHI das origens: {c.fmt.num(r['hhi_origem'])} · {r['n_paises']} países · {c.fmt.usd_compact(r['fob_usd'])} FOB. {unit_txt}"
    )

# ------------------------------------------------------------------ ponte ----
c.section("Preço de importação × preço público", "compare_arrows")
ponte = c.table("ponte_preco_importacao")
comp = ponte.filter(pl.col("comparavel_por_unidade"))
for r in comp.iter_rows(named=True):
    with st.container(key=f"rx-panel-ponte-{r['familia_macro']}"):
        a, b, d = st.columns(3)
        a.metric(
            f"CIF de importação ({r['anos_importacao']})",
            c.fmt.brl(r["preco_cif_brl_real_unid"], 0),
            help="Valor CIF ÷ unidades importadas, convertido pelo câmbio médio mensal e deflacionado.",
        )
        b.metric(
            "Mediana paga pelo setor público",
            c.fmt.brl(r["preco_publico_mediana"], 0),
            help=f"{r['n_compras_publico']} compras, {r['periodo_publico']}, itens {r['itens_catmat']}.",
        )
        d.metric("Razão público ÷ importação", c.fmt.ratio(r["razao_publico_importacao"]))
        st.markdown(
            f"**{r['familia_macro']}** (NCM {r['ncms']}). O que existe entre um preço e outro:"
        )
        st.markdown("\n".join(f"- {x}" for x in r["componentes_diferenca"].split("; ")))
        st.caption(
            "A ponte é contexto, não acusação: o preço público inclui custos que o CIF não tem. Agregados diferentes (todo o NCM × itens do catálogo)."
        )
nc = ponte.filter(~pl.col("comparavel_por_unidade")).select(
    pl.col("familia_macro").alias("Família"),
    pl.col("ncms").alias("NCM"),
    pl.col("unidade_estatistica").alias("Unidade estatística"),
    pl.col("preco_cif_usd_kg").round(2).alias("CIF (US$/kg)"),
    pl.col("nota").alias("Por que não comparar"),
)
st.dataframe(
    nc,
    hide_index=True,
    column_config={"CIF (US$/kg)": st.column_config.NumberColumn(format="localized")},
)

# ----------------------------------------------------------------- ANVISA ----
anv = c.table("anvisa_registros_familia")
if anv.height:
    c.section("Registros na ANVISA: fabricante estrangeiro", "verified")
    a = anv.sort("share_so_estrangeiro")
    fig = go.Figure(
        go.Bar(
            x=a["share_so_estrangeiro"].to_list(),
            y=a["familia_macro"].to_list(),
            orientation="h",
            marker_color=c.theme.ACCENT,
            customdata=a["registros_vigentes"].to_list(),
            hovertemplate="%{y}: %{x:.0%} de %{customdata} registros<extra></extra>",
        )
    )
    fig.update_xaxes(
        tickformat=".0%", range=[0, 1], title="Registros vigentes só com fabricante estrangeiro"
    )
    fig.update_layout(**c.theme.plotly_layout(height=340, title="Dependência tecnológica (proxy)"))
    c.plot(fig)
    st.caption(
        "Fonte: ANVISA, dados abertos de produtos para saúde. Registro não mede volume vendido."
    )
c.footer()
