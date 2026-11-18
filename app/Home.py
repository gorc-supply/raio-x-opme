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
    c.ui.hero(
        "Raio-X OPME",
        "Quanto o setor público brasileiro paga por stents, próteses e implantes, como o preço varia "
        "entre estados e quanto disso depende de importação.",
    )
    f = c.filters()
    if not m or not f:
        st.info("Ainda não há dados processados. Rode `uv run raiox all`.")
        return
    comp = c.filtered_purchases(f, item=False)
    p0, p1 = f["periodo"]
    c.ui.kpis(
        [
            (
                "inventory_2",
                "Itens monitorados",
                c.fmt.num(comp["codigo_catmat"].n_unique()),
                "Itens CATMAT do catálogo curado (config/itens_opme.yaml) no filtro atual.",
            ),
            (
                "shopping_cart",
                "Compras analisadas",
                c.fmt.num(comp["id_compra"].n_unique()),
                "Compras distintas (idCompra) no período e filtros escolhidos.",
            ),
            ("map", "UFs cobertas", c.fmt.num(comp["uf"].n_unique()), None),
            (
                "calendar_month",
                "Período",
                f"{c.fmt.MESES[p0.month - 1]}/{p0:%y} – {c.fmt.MESES[p1.month - 1]}/{p1:%y}",
                f"Mês da compra: {c.fmt.month(p0)} a {c.fmt.month(p1)}. Padrão: últimos 24 meses completos.",
            ),
        ]
    )

    c.section("Principais achados", "lightbulb")
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
    for i, (col, r) in enumerate(zip(cols, fortes.head(3).iter_rows(named=True), strict=False)):
        with col:
            c.ui.finding_card(r, key=str(i))

    with st.expander("Todos os achados (inclusive moderados e fracos)", icon=":material/list_alt:"):
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

    c.section("Como ler este painel", "help")
    st.markdown(
        f"""
- **Comparação justa:** só o mesmo código CATMAT, na mesma unidade. Preços em R$ de {c.ref_month()} (IPCA).
- **Amostra mínima:** uma UF só entra em comparação com pelo menos {m["regras"]["min_compras_uf"]} compras e {m["regras"]["min_orgaos_uf"]} órgãos compradores.
- **Mediana**, nunca média, como medida central. Outliers são marcados (não apagados) e ficam fora por padrão.
- **Diferença não é irregularidade:** volume, prazo, logística, consignação e especificação explicam boa parte da variação.
"""
    )
    with st.expander("Metadados da base", icon=":material/data_object:"):
        st.code(json.dumps(m, ensure_ascii=False, indent=1), language="json")
    c.footer()


home()
