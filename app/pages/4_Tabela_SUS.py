"""Tabela SUS (SIGTAP) × preço praticado nas compras públicas."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _common as c  # noqa: E402

c.setup_page("Tabela SUS × preço")
c.filters()
c.page_title("Tabela SUS × preço praticado", "receipt_long")
ponte = c.table("ponte_sigtap_preco")
if ponte.height == 0:
    st.info(
        "Sem dados do SIGTAP na gold. Rode `uv run raiox ingest complementares` e `uv run raiox analyze`."
    )
    st.stop()

r0 = ponte.row(0, named=True)
comp_lbl = f"{r0['competencia_sigtap'][4:]}/{r0['competencia_sigtap'][:4]}"
st.markdown(
    f"""
O **SIGTAP** (Tabela de Procedimentos, Medicamentos e OPM do SUS) diz quanto o SUS **reembolsa** ao
hospital por unidade de OPME usada num procedimento. **Não é preço de compra**: o hospital compra do
fornecedor pelo preço que conseguir e recebe do SUS o valor de tabela.

- **Preço praticado acima da tabela** → o reembolso não cobre a compra: a diferença indica
  **defasagem da tabela**, não conduta de quem compra.
- **Preço praticado abaixo da tabela** → o valor de tabela cobre a mediana paga.

Valor de tabela da competência **{comp_lbl}**; preço praticado = mediana das compras públicas de
{r0["periodo_inicio"]:%m/%Y} a {r0["periodo_fim"]:%m/%Y}, sem outliers, em R$ de {c.ref_month()} (IPCA).
"""
)
if not r0["mapa_validado"]:
    st.warning(
        "O mapa entre códigos SIGTAP e itens CATMAT (`config/mapa_sigtap_catmat.yaml`) ainda **não foi "
        "validado** pelo autor. Até lá, nenhuma comparação preço × tabela passa de robustez moderada.",
        icon=":material/rule:",
    )

conf = st.segmented_control(
    "Confiança do mapeamento",
    ["alta", "media", "baixa"],
    selection_mode="multi",
    default=["alta"],
    format_func=lambda x: {"alta": "alta", "media": "média", "baixa": "baixa"}[x],
    key="sus_conf",
    help="Alta: mesmo dispositivo e componente. Média: o código SIGTAP agrupa itens que o CATMAT separa. "
    "Baixa: correspondência aproximada. Só os pares de confiança alta viram achado.",
)
view = ponte.filter(
    pl.col("confianca").is_in(conf or ["alta"]) & pl.col("razao_preco_sigtap").is_not_null()
)

# ------------------------------------------------------- razão com IC ----
if view.height:
    v = view.sort("razao_preco_sigtap")
    labels = [f"{n} ({cf})" for n, cf in zip(v["nome_curto"], v["confianca"], strict=True)]
    colors = [
        c.theme.ACCENT if lo > 1 else c.theme.LOW if hi < 1 else c.theme.MUTED
        for lo, hi in zip(v["ic_inf"], v["ic_sup"], strict=True)
    ]
    fig = go.Figure(
        go.Scatter(
            x=v["razao_preco_sigtap"].to_list(),
            y=labels,
            mode="markers",
            marker={"size": 13, "color": colors, "line": {"width": 1, "color": "white"}},
            error_x={
                "type": "data",
                "symmetric": False,
                "array": (v["ic_sup"] - v["razao_preco_sigtap"]).to_list(),
                "arrayminus": (v["razao_preco_sigtap"] - v["ic_inf"]).to_list(),
                "color": c.theme.MUTED,
                "thickness": 1.5,
            },
            customdata=list(
                zip(
                    v["mediana_preco_real"].to_list(),
                    v["valor_sigtap_nominal"].to_list(),
                    v["n_compras"].to_list(),
                    v["codigo_sigtap_fmt"].to_list(),
                    strict=True,
                )
            ),
            hovertemplate="%{y}<br>Preço ÷ tabela: %{x:.2f}×<br>Mediana: R$ %{customdata[0]:,.2f}"
            "<br>Tabela SUS (%{customdata[3]}): R$ %{customdata[1]:,.2f}<br>n = %{customdata[2]} compras"
            "<extra></extra>",
        )
    )
    fig.add_vline(x=1, line_dash="dash", line_color=c.theme.INK, annotation_text="= tabela")
    fig.update_xaxes(
        type="log", title="Mediana paga ÷ valor da Tabela SUS (escala log; barras = IC 95%)"
    )
    fig.update_layout(
        **c.theme.plotly_layout(
            height=max(320, 42 * v.height + 120), title="Preço praticado ÷ Tabela SUS, por item"
        )
    )
    st.plotly_chart(fig, config={"displayModeBar": False})
    st.caption(
        "Cor: acima da tabela (IC todo acima de 1), abaixo (IC todo abaixo de 1) ou indistinguível. "
        "Intervalo por bootstrap das compras."
    )

# ------------------------------------------------------------ tabela ----
show = view.select(
    pl.col("nome_curto").alias("Item (CATMAT)"),
    pl.col("codigo_catmat").alias("CATMAT"),
    pl.col("codigo_sigtap_fmt").alias("SIGTAP"),
    pl.col("descricao_sigtap").alias("Procedimento SIGTAP"),
    pl.col("confianca").alias("Confiança"),
    pl.col("valor_sigtap_nominal").alias("Tabela SUS (R$)"),
    pl.col("mediana_preco_real").alias("Mediana paga (R$)"),
    pl.col("razao_preco_sigtap").alias("Preço ÷ tabela"),
    pl.col("n_compras").alias("Compras"),
    pl.col("justificativa").alias("Por que este par"),
)
st.dataframe(
    show,
    hide_index=True,
    column_config={
        "Tabela SUS (R$)": st.column_config.NumberColumn(format="localized"),
        "Mediana paga (R$)": st.column_config.NumberColumn(format="localized"),
        "Preço ÷ tabela": st.column_config.NumberColumn(format="%.2f×"),
        "Por que este par": st.column_config.TextColumn(width="large"),
    },
)

# --------------------------------------------- evolução do valor de tabela ----
serie = c.table("sigtap_serie")
if serie.height:
    c.section("Evolução do valor de tabela", "timeline")
    codes = (
        ponte.filter(pl.col("confianca").is_in(conf or ["alta"]))
        .select("codigo_sigtap", "codigo_sigtap_fmt", "descricao_sigtap")
        .unique(subset="codigo_sigtap", keep="first", maintain_order=True)
    )
    opts = {
        r["codigo_sigtap"]: f"{r['codigo_sigtap_fmt']} — {r['descricao_sigtap']}"
        for r in codes.iter_rows(named=True)
    }
    if opts:
        code = st.selectbox(
            "Procedimento SIGTAP", list(opts), format_func=lambda x: opts[x], key="sus_code"
        )
        s = serie.filter(pl.col("codigo_sigtap") == code).sort("mes_competencia")
        fig2 = go.Figure()
        fig2.add_trace(
            go.Scatter(
                x=s["mes_competencia"].to_list(),
                y=s["valor_real"].to_list(),
                mode="lines+markers",
                name=f"Real (R$ de {c.ref_month()})",
                line={"color": c.theme.PRIMARY, "width": 3},
                hovertemplate="%{x|%m/%Y}: R$ %{y:,.2f}<extra>real</extra>",
            )
        )
        fig2.add_trace(
            go.Scatter(
                x=s["mes_competencia"].to_list(),
                y=s["valor_nominal"].to_list(),
                mode="lines+markers",
                name="Nominal",
                line={"color": c.theme.MUTED, "dash": "dot", "shape": "hv"},
                hovertemplate="%{x|%m/%Y}: R$ %{y:,.2f}<extra>nominal</extra>",
            )
        )
        fig2.update_yaxes(title="R$ por unidade de OPME", tickformat=",.0f", rangemode="tozero")
        fig2.update_layout(
            **c.theme.plotly_layout(
                height=380,
                title="Valor de tabela: nominal × real",
                legend={"orientation": "h", "y": -0.2},
            )
        )
        st.plotly_chart(fig2, config={"displayModeBar": False})
        st.caption(
            "Competências de janeiro de cada ano desde 2015 e a mais recente. Valor real corrigido pelo IPCA."
        )
st.caption(
    "Fonte da tabela: SIGTAP/DATASUS (Tabela Unificada do SUS), licença CC BY 3.0. Mapa SIGTAP × CATMAT: curadoria do projeto."
)
c.footer()
