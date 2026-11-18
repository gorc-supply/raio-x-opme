"""Relatório de qualidade: linhas por fonte, descartes por motivo, cobertura item × UF
e período efetivo. Gera data/gold/qualidade.parquet e docs/QUALIDADE.md."""

from __future__ import annotations

import json

import polars as pl

from raiox.analytics.dispersion import analysis_period
from raiox.bronze import read_bronze
from raiox.config import Settings
from raiox.logs import logger

MOTIVOS = {
    "duplicatas": "Duplicata (mesma compra + item + CATMAT; mantida a atualização mais recente)",
    "descarte_fora_do_catalogo": "CATMAT fora do catálogo curado",
    "descarte_preco_invalido": "Preço ≤ 0 ou ausente",
    "descarte_quantidade_invalida": "Quantidade ≤ 0 ou ausente",
    "descarte_data_ausente": "Data da compra ausente",
    "descarte_uf_invalida": "UF ausente ou inválida",
    "descarte_unidade_ausente": "Unidade de fornecimento ausente",
    "descarte_capacidade_ambigua": "Capacidade da unidade ambígua (ex.: UN com capacidade > 1)",
    "descarte_embalagem_sem_capacidade": "Embalagem sem capacidade informada",
    "descarte_embalagem_sem_unidade_medida": "Embalagem sem unidade de medida em peças",
    "descarte_unidade_desconhecida": "Unidade de fornecimento desconhecida",
    "descarte_unidade_incompativel": "Unidade diferente da unidade dominante do item",
}


def build_quality(settings: Settings) -> pl.DataFrame:
    silver = settings.path("silver")
    counts = json.loads((silver / "_contagens.json").read_text(encoding="utf-8"))
    comp = pl.read_parquet(silver / "compras_precos.parquet")
    period = analysis_period(comp, settings.analysis)
    rows: list[dict] = []

    def add(
        secao: str, chave: str, valor: float | None, subchave: str = "", texto: str = ""
    ) -> None:
        rows.append(
            {
                "secao": secao,
                "chave": chave,
                "subchave": subchave,
                "valor": None if valor is None else float(valor),
                "texto": texto,
            }
        )

    for table in (
        "compras_precos",
        "catmat_itens",
        "comex_import",
        "comex_export",
        "ipca",
        "cambio",
        "ufs",
    ):
        b = read_bronze(settings, table)
        add(
            "linhas_bronze",
            table,
            b.height,
            texto=", ".join(sorted(b["_snapshot"].unique().to_list())) if b.height else "",
        )
    for name in (
        "compras_precos",
        "compras_descartes",
        "comex_import",
        "comex_export",
        "ipca",
        "cambio",
        "ufs",
    ):
        p = silver / f"{name}.parquet"
        add("linhas_silver", name, pl.read_parquet(p).height if p.exists() else 0)

    cc = counts.get("compras", {})
    for key, label in MOTIVOS.items():
        if key in cc:
            add("descartes", key.removeprefix("descarte_"), cc[key], texto=label)
    add("outliers", "marcados", int(comp["outlier"].sum()), texto="IQR 3× em log OU MAD > 3,5")
    add("outliers", "iqr", int(comp["outlier_iqr"].sum()))
    add("outliers", "mad", int(comp["outlier_mad"].sum()))
    add(
        "lgpd",
        "fornecedores_pf_mascarados",
        int(comp["fornecedor_pf"].sum()),
        texto="CPF mascarado e nome substituído",
    )

    add("periodo", "dados_inicio", None, texto=comp["data_compra"].min().isoformat())
    add("periodo", "dados_fim", None, texto=comp["data_compra"].max().isoformat())
    add("periodo", "analise", None, texto=period.label)

    per = period.filter(comp)
    cov = per.group_by(["codigo_catmat", "nome_curto", "uf"], maintain_order=True).agg(
        pl.col("id_compra").n_unique().alias("n")
    )
    for r in cov.iter_rows(named=True):
        add("cobertura", str(r["codigo_catmat"]), r["n"], subchave=r["uf"], texto=r["nome_curto"])

    df = pl.DataFrame(
        rows,
        schema={
            "secao": pl.String,
            "chave": pl.String,
            "subchave": pl.String,
            "valor": pl.Float64,
            "texto": pl.String,
        },
    )
    gold = settings.path("gold")
    gold.mkdir(parents=True, exist_ok=True)
    from raiox.pipeline import stable_floats

    stable_floats(df).write_parquet(gold / "qualidade.parquet", statistics=False)

    md = render_markdown(df, cov, period.label, settings)
    target = (
        settings.path("gold") if settings.offline else settings.root / "docs"
    ) / "QUALIDADE.md"
    target.write_text(md, encoding="utf-8")
    logger.info("Qualidade: {} linhas → qualidade.parquet e {}", df.height, target.name)
    return df


def _fmt(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.0f}".replace(",", ".")


def render_markdown(
    df: pl.DataFrame, cov: pl.DataFrame, period_label: str, settings: Settings
) -> str:
    lines = [
        "# Relatório de qualidade dos dados",
        "",
        "Gerado por `uv run raiox quality`. Valores recalculados a cada execução do pipeline.",
        "",
        f"**Período de análise:** {period_label}",
        "",
        "## Linhas por fonte",
        "",
        "| Tabela | Bronze (todos os snapshots) | Silver |",
        "|---|---:|---:|",
    ]
    b = {
        r["chave"]: r["valor"]
        for r in df.filter(pl.col("secao") == "linhas_bronze").iter_rows(named=True)
    }
    s = {
        r["chave"]: r["valor"]
        for r in df.filter(pl.col("secao") == "linhas_silver").iter_rows(named=True)
    }
    for k in sorted(set(b) | set(s)):
        lines.append(f"| {k} | {_fmt(b.get(k))} | {_fmt(s.get(k))} |")
    lines += ["", "## Descartes por motivo (preços)", "", "| Motivo | Linhas |", "|---|---:|"]
    for r in df.filter(pl.col("secao") == "descartes").iter_rows(named=True):
        lines.append(f"| {r['texto']} | {_fmt(r['valor'])} |")
    lines += ["", "## Outliers e LGPD", "", "| Indicador | Linhas |", "|---|---:|"]
    for r in df.filter(pl.col("secao").is_in(["outliers", "lgpd"])).iter_rows(named=True):
        lines.append(f"| {r['secao']}: {r['chave']} | {_fmt(r['valor'])} |")
    per = {
        r["chave"]: r["texto"]
        for r in df.filter(pl.col("secao") == "periodo").iter_rows(named=True)
    }
    lines += [
        "",
        "## Período efetivo",
        "",
        f"- Compras mais antiga e mais recente na base: {per.get('dados_inicio')} a {per.get('dados_fim')}",
        f"- Janela usada nas comparações: {per.get('analise')}",
        "",
        "## Cobertura item × UF (compras distintas no período)",
        "",
        f"Células vazias = sem compras. UF entra em comparação com ≥ {settings.analysis.min_purchases_per_uf} compras e ≥ {settings.analysis.min_buyers_per_uf} órgãos.",
        "",
    ]
    if cov.height:
        piv = cov.pivot(
            on="uf", index=["codigo_catmat", "nome_curto"], values="n", sort_columns=True
        ).sort("codigo_catmat")
        ufs = [c for c in piv.columns if c not in ("codigo_catmat", "nome_curto")]
        lines.append("| Item | " + " | ".join(ufs) + " |")
        lines.append("|---|" + "---:|" * len(ufs))
        for r in piv.iter_rows(named=True):
            cells = ["" if r[u] is None else str(r[u]) for u in ufs]
            lines.append(
                f"| {r['nome_curto']} ({r['codigo_catmat']}) | " + " | ".join(cells) + " |"
            )
    return "\n".join(lines) + "\n"
