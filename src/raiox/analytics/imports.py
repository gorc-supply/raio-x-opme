"""Importação por NCM (volumes, preço implícito, origens, HHI, balança) e a ponte
"preço de importação × preço público" (seção 8.8).

Preço unitário implícito = FOB (ou CIF) ÷ quantidade estatística, SOMENTE quando a
unidade estatística do NCM é "unidade". Para NCMs em kg, o preço é por kg e não é
comparado diretamente com preço por peça. A ponte é contexto, nunca acusação.
"""

from __future__ import annotations

import json

import polars as pl

from raiox.analytics.dispersion import Period
from raiox.transform.deflate import deflate

# O que existe entre o preço CIF de importação e o preço pago pelo setor público.
BRIDGE_COMPONENTS = [
    "tributos de importação e internos (II, IPI, PIS/Cofins-importação, ICMS)",
    "despacho aduaneiro, frete interno e armazenagem",
    "registro sanitário na ANVISA e custos regulatórios",
    "consignação (estoque parado em hospitais) e reposição",
    "instrumental cirúrgico emprestado ao hospital",
    "instrumentador e suporte técnico em sala",
    "margem de distribuição",
    "prazo de pagamento do setor público (custo financeiro)",
]


def _unit_map(ncm_table: list[dict] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for r in ncm_table or []:
        unit = str(r.get("unit", "")).upper()
        out[str(r.get("coNcm"))] = "UN" if "UNIDADE" in unit else "KG"
    return out


def load_ncm_units(reference_dir) -> dict[str, str]:
    path = reference_dir / "comex_ncm_9018_9021.json"
    if not path.exists():
        return {}
    return _unit_map(json.loads(path.read_text(encoding="utf-8")))


def _with_brl(imp: pl.DataFrame, cambio: pl.DataFrame, index: pl.DataFrame) -> pl.DataFrame:
    df = imp.join(cambio.select("mes", "usd_brl"), on="mes", how="left")
    df = df.with_columns(
        (pl.col("fob_usd") * pl.col("usd_brl")).alias("fob_brl"),
        (pl.col("cif_usd") * pl.col("usd_brl")).alias("cif_brl"),
    )
    return deflate(df, "mes", ["fob_brl", "cif_brl"], index)


def importacao_ncm_ano(
    imp: pl.DataFrame,
    exp: pl.DataFrame,
    cambio: pl.DataFrame,
    index: pl.DataFrame,
    units: dict[str, str],
    top_n: int,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Retorna (importacao_ncm_ano, importacao_origem)."""
    df = _with_brl(imp, cambio, index)
    keys = ["ncm", "descricao_ncm", "familia_macro", "ncm_historico", "ano"]
    agg = df.group_by(keys).agg(
        pl.col("mes").n_unique().cast(pl.Int64).alias("meses_com_dados"),
        pl.col("mes").max().alias("ultimo_mes"),
        *[
            pl.col(c).sum()
            for c in (
                "fob_usd",
                "cif_usd",
                "frete_usd",
                "seguro_usd",
                "kg",
                "qtd_estatistica",
                "fob_brl",
                "cif_brl",
                "cif_brl_real",
            )
        ],
    )
    by_country = (
        df.group_by(["ncm", "familia_macro", "ano", "pais"])
        .agg(pl.col("fob_usd").sum(), pl.col("cif_usd").sum(), pl.col("kg").sum())
        .with_columns(
            (pl.col("fob_usd") / pl.col("fob_usd").sum().over(["ncm", "ano"])).alias(
                "participacao_fob"
            )
        )
        .with_columns(
            pl.col("participacao_fob")
            .rank("ordinal", descending=True)
            .over(["ncm", "ano"])
            .cast(pl.Int64)
            .alias("rank")
        )
        .sort("ncm", "ano", "rank")
    )
    conc = by_country.group_by(["ncm", "ano"]).agg(
        ((pl.col("participacao_fob") * 100) ** 2).sum().alias("hhi_origem"),
        pl.col("participacao_fob").filter(pl.col("rank") <= top_n).sum().alias(f"cr{top_n}_origem"),
        pl.col("pais").n_unique().cast(pl.Int64).alias("n_paises"),
        pl.col("pais").filter(pl.col("rank") == 1).first().alias("pais_principal"),
        pl.col("participacao_fob")
        .filter(pl.col("rank") == 1)
        .first()
        .alias("share_pais_principal"),
        pl.concat_str(
            [
                pl.col("pais"),
                pl.lit(" ("),
                (pl.col("participacao_fob") * 100).round(0).cast(pl.Int64).cast(pl.String),
                pl.lit("%)"),
            ]
        )
        .filter(pl.col("rank") <= top_n)
        .str.join(", ")
        .alias("top_paises"),
    )
    expo = (
        exp.group_by(["ncm", "ano"]).agg(pl.col("fob_usd").sum().alias("export_fob_usd"))
        if exp.height
        else pl.DataFrame(schema={"ncm": pl.String, "ano": pl.Int32, "export_fob_usd": pl.Float64})
    )
    out = (
        agg.join(conc, on=["ncm", "ano"], how="left")
        .join(expo, on=["ncm", "ano"], how="left")
        .with_columns(
            pl.col("export_fob_usd").fill_null(0.0),
            pl.col("ncm").replace_strict(units, default="KG").alias("unidade_estatistica"),
        )
        .with_columns(
            (pl.col("export_fob_usd") - pl.col("fob_usd")).alias("saldo_fob_usd"),
            (pl.col("export_fob_usd") / pl.col("fob_usd")).alias("cobertura_exportacao"),
            pl.when(pl.col("unidade_estatistica") == "UN")
            .then(pl.col("fob_usd") / pl.col("qtd_estatistica"))
            .alias("preco_fob_usd_unid"),
            pl.when(pl.col("unidade_estatistica") == "UN")
            .then(pl.col("cif_usd") / pl.col("qtd_estatistica"))
            .alias("preco_cif_usd_unid"),
            pl.when(pl.col("unidade_estatistica") == "UN")
            .then(pl.col("cif_brl_real") / pl.col("qtd_estatistica"))
            .alias("preco_cif_brl_real_unid"),
            (pl.col("fob_usd") / pl.col("kg")).alias("preco_fob_usd_kg"),
            (pl.col("cif_usd") / pl.col("kg")).alias("preco_cif_usd_kg"),
            pl.lit(index["mes"].max()).alias("mes_ref"),
        )
        .with_columns(pl.col("ano").cast(pl.Int32))
        .sort("ncm", "ano")
    )
    return out, by_country


def ponte_preco_importacao(
    imp_ano: pl.DataFrame,
    puf: pl.DataFrame,
    silver: pl.DataFrame,
    period: Period,
    bridge_years: int,
) -> pl.DataFrame:
    """Por família macro: preço CIF implícito (R$ reais) vs. mediana do preço público."""
    full_years = imp_ano.filter(pl.col("meses_com_dados") == 12)
    last_full = full_years["ano"].max() if full_years.height else imp_ano["ano"].max()
    years = list(range(last_full - bridge_years + 1, last_full + 1))
    cur = imp_ano.filter(pl.col("ano").is_in(years) & ~pl.col("ncm_historico").fill_null(False))
    pub = period.filter(silver).filter(~pl.col("outlier") & pl.col("preco_real").is_not_null())
    rows = []
    for fam in sorted(cur["familia_macro"].drop_nulls().unique().to_list()):
        g = cur.filter(pl.col("familia_macro") == fam)
        un = g.filter(pl.col("unidade_estatistica") == "UN")
        p = pub.filter(pl.col("familia_macro") == fam)
        itens = sorted(p["codigo_catmat"].unique().to_list())
        comparable = un.height > 0 and p.height > 0
        cif_unid = (
            float(un["cif_brl_real"].sum() / un["qtd_estatistica"].sum())
            if un.height and un["qtd_estatistica"].sum() > 0
            else None
        )
        mediana_pub = float(p["preco_real"].median()) if p.height else None
        rows.append(
            {
                "familia_macro": fam,
                "ncms": ", ".join(sorted(g["ncm"].unique().to_list())),
                "anos_importacao": f"{years[0]}" if len(years) == 1 else f"{years[0]}–{years[-1]}",
                "unidade_estatistica": "UN" if un.height else "KG",
                "importacao_cif_usd": float(g["cif_usd"].sum()),
                "importacao_qtd_unidades": float(un["qtd_estatistica"].sum())
                if un.height
                else None,
                "importacao_kg": float(g["kg"].sum()),
                "preco_cif_brl_real_unid": cif_unid,
                "preco_cif_usd_kg": float(g["cif_usd"].sum() / g["kg"].sum())
                if g["kg"].sum() > 0
                else None,
                "preco_publico_mediana": mediana_pub,
                "n_compras_publico": int(p["id_compra"].n_unique()) if p.height else 0,
                "n_registros_publico": p.height,
                "itens_catmat": ", ".join(str(i) for i in itens),
                "periodo_publico": period.label,
                "comparavel_por_unidade": comparable,
                "razao_publico_importacao": (mediana_pub / cif_unid)
                if comparable and cif_unid
                else None,
                "diferenca_reais": (mediana_pub - cif_unid) if comparable and cif_unid else None,
                "componentes_diferenca": "; ".join(BRIDGE_COMPONENTS),
                "nota": (
                    "Comparação por peça: NCM com unidade estatística em unidades."
                    if comparable
                    else "Sem comparação direta: a unidade estatística do NCM é kg (ou não há compras públicas da família no catálogo)."
                ),
                "mes_ref": imp_ano["mes_ref"][0],
            }
        )
    del puf
    return pl.DataFrame(rows, infer_schema_length=None)
