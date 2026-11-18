"""Raio-X OPME — painel (arquivo principal do Streamlit): página inicial."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402

c.setup_page("Início")


def home() -> None:
    m = c.meta()
    st.title("Raio-X OPME")
    st.markdown(
        "**Quanto o setor público brasileiro paga por stents, próteses e implantes — "
        "e quanto disso depende de importação.**"
    )
    f = c.filters()
    if not m or not f:
        st.info("Ainda não há dados processados. Rode `uv run raiox all`.")
        return
    comp = c.filtered_purchases(f, item=False)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric(
        "Itens monitorados",
        c.fmt.num(comp["codigo_catmat"].n_unique()),
        help="Itens CATMAT do catálogo curado (config/itens_opme.yaml) no filtro atual.",
    )
    k2.metric(
        "Compras analisadas",
        c.fmt.num(comp["id_compra"].n_unique()),
        help="Compras distintas (idCompra) no período e filtros escolhidos.",
    )
    k3.metric("UFs cobertas", c.fmt.num(comp["uf"].n_unique()))
    p0, p1 = f["periodo"]
    k4.metric(
        "Período",
        f"{p0:%m/%Y}–{p1:%m/%Y}",
        help="Mês da compra. Padrão: últimos 24 meses completos.",
    )

    st.subheader("Principais achados")
    st.caption(
        "Só achados de robustez **forte** (passam em todas as regras estatísticas da metodologia)."
    )
    ach = c.table("achados")
    fortes = ach.filter(pl.col("robustez") == "forte").sort("rank")
    if f["familia"] != "Todas":
        fam_macro = (
            comp["familia_macro"].first()
            if "familia_macro" in comp.columns and comp.height
            else None
        )
        sel = fortes.filter((pl.col("familia") == f["familia"]) | (pl.col("familia") == fam_macro))
        fortes = sel if sel.height else fortes
    cols = st.columns(3)
    for col, r in zip(cols, fortes.head(3).iter_rows(named=True), strict=False):
        with col.container(border=True):
            st.markdown(f"**{r['titulo']}**")
            st.write(r["frase"])
            st.caption(f"n: {r['n_descricao']} · Período: {r['periodo']} · Fonte: {r['fonte']}")

    with st.expander("Todos os achados (inclusive moderados e fracos)"):
        rob = st.segmented_control(
            "Robustez",
            ["forte", "moderado", "fraco"],
            selection_mode="multi",
            default=["forte", "moderado"],
            key="home_rob",
        )
        view = ach.filter(pl.col("robustez").is_in(rob or ["forte"])).select(
            "rank", "robustez", "titulo", "n_descricao", "periodo", "fonte", "motivo_robustez"
        )
        st.dataframe(
            view,
            hide_index=True,
            column_config={
                "rank": "#",
                "robustez": "Robustez",
                "titulo": st.column_config.TextColumn("Achado", width="large"),
                "n_descricao": "Base (n)",
                "periodo": "Período",
                "fonte": "Fonte",
                "motivo_robustez": "Por que esta robustez",
            },
        )
        st.caption(
            "Moderado = indício que merece investigação, com ressalva. Fraco = não publicar."
        )

    st.subheader("Como ler este painel")
    st.markdown(
        f"""
- **Comparação justa:** só o mesmo código CATMAT, na mesma unidade. Preços em R$ de {c.ref_month()} (IPCA).
- **Amostra mínima:** uma UF só entra em comparação com pelo menos {m["regras"]["min_compras_uf"]} compras e {m["regras"]["min_orgaos_uf"]} órgãos compradores.
- **Mediana**, nunca média, como medida central. Outliers são marcados (não apagados) e ficam fora por padrão.
- **Diferença não é irregularidade:** volume, prazo, logística, consignação e especificação explicam boa parte da variação.
"""
    )
    with st.expander("Metadados da base"):
        st.code(json.dumps(m, ensure_ascii=False, indent=1), language="json")
    c.footer()


home()
