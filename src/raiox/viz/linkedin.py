"""Kit de LinkedIn: 5+ gráficos PNG 1080×1350 (4:5) e carrossel em PDF (PdfPages, sem kaleido).

Regras: título = a própria conclusão; rodapé padrão da seção 9; todo número com período,
n e fonte; a robustez do achado aparece no próprio gráfico. Itens são escolhidos por regra
(robustez, homogeneidade, IC), nunca à mão.
"""

from __future__ import annotations

import json
import textwrap
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator, NullFormatter  # noqa: E402

from raiox import fmt  # noqa: E402
from raiox.config import Settings  # noqa: E402
from raiox.logs import logger  # noqa: E402
from raiox.viz import theme  # noqa: E402

ROB_ORDER = {"forte": 0, "moderado": 1, "fraco": 2, "sem_comparacao": 3}
ROB_LABEL = {
    "forte": "Robustez FORTE: passa em todas as regras estatísticas",
    "moderado": "Robustez MODERADA: indício que merece investigação, com ressalva",
    "fraco": "Robustez FRACA: não serve como conclusão",
}


class Ctx:
    def __init__(self, settings: Settings):
        self.s = settings
        self.gold = settings.path("gold")
        self.meta = json.loads((self.gold / "meta.json").read_text(encoding="utf-8"))
        self.ref = fmt.month(date.fromisoformat(self.meta["mes_ref_deflacao"]))
        self.period = self.meta["periodo_label"]
        self.w = settings.charts.width_px / settings.charts.dpi
        self.h = settings.charts.height_px / settings.charts.dpi
        self.dpi = settings.charts.dpi
        self.footer = settings.charts.footer.format(ref_month=self.ref)
        self.url = settings.project.dashboard_url

    def t(self, name: str) -> pl.DataFrame:
        p = self.gold / f"{name}.parquet"
        return pl.read_parquet(p) if p.exists() else pl.DataFrame()


def brl_axis(nd: int = 0) -> FuncFormatter:
    return FuncFormatter(lambda v, _: fmt.brl(v, nd))


def _wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width=width))


TITLE_WRAP, SUB_WRAP = 28, 56


def new_fig(ctx: Ctx, title: str, subtitle: str = "", extra_source: str = ""):
    plt.rcParams.update(theme.mpl_rc())
    fig = plt.figure(figsize=(ctx.w, ctx.h), dpi=ctx.dpi)
    t_lines = textwrap.wrap(title, TITLE_WRAP)
    fig.text(
        0.06,
        0.965,
        "\n".join(t_lines),
        ha="left",
        va="top",
        fontsize=25,
        fontweight="bold",
        color=theme.INK,
        linespacing=1.12,
    )
    y_sub = 0.965 - 0.046 * len(t_lines) - 0.015
    s_lines = textwrap.wrap(subtitle, SUB_WRAP) if subtitle else []
    if s_lines:
        fig.text(
            0.06,
            y_sub,
            "\n".join(s_lines),
            ha="left",
            va="top",
            fontsize=14.5,
            color=theme.MUTED,
            linespacing=1.3,
        )
    foot = ctx.footer + (f" {extra_source}" if extra_source else "")
    fig.text(
        0.06,
        0.035,
        _wrap(foot, 92),
        ha="left",
        va="bottom",
        fontsize=9.5,
        color=theme.MUTED,
        linespacing=1.3,
    )
    fig.text(
        0.94,
        0.012,
        "Raio-X OPME · " + ctx.url.removeprefix("https://"),
        ha="right",
        va="bottom",
        fontsize=9.5,
        color=theme.PRIMARY,
    )
    top = y_sub - 0.029 * len(s_lines) - 0.045
    return fig, top


def badge(fig, robustez: str, y: float = 0.115) -> None:
    color = theme.ROBUSTEZ.get(robustez, theme.FRACO)
    fig.text(
        0.06,
        y,
        ROB_LABEL.get(robustez, robustez),
        fontsize=11.5,
        color=theme.DARK,  # texto escuro sobre coral/âmbar/cinza: contraste ≥ 4,5:1
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.45", "fc": color, "ec": color},
    )


def save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=fig.dpi, metadata={"Software": None})
    plt.close(fig)
    return path


# --------------------------------------------------------- escolha do item ----
def pick_dispersion_item(disp: pl.DataFrame) -> dict | None:
    """Item com a dispersão entre UFs mais robusta: robustez, depois homogêneo, depois IC inferior."""
    d = disp.filter(pl.col("robustez") != "sem_comparacao")
    if d.height == 0:
        return None
    d = d.with_columns(
        pl.col("robustez").replace_strict(ROB_ORDER, return_dtype=pl.Int64).alias("_r"),
        (pl.col("top_orgao_share_max").fill_null(1).clip(0, 1) > 0.5).alias("_dom"),
    ).sort(["_r", "item_heterogeneo", "_dom", "ic_inf"], descending=[False, False, False, True])
    return d.row(0, named=True)


# ------------------------------------------------------------ 1. ranking UF ----
def chart_ranking(ctx: Ctx, out: Path) -> Path | None:
    disp = ctx.t("dispersao_item")
    r = pick_dispersion_item(disp)
    if r is None:
        return None
    puf = ctx.t("preco_item_uf").filter(
        (pl.col("codigo_catmat") == r["codigo_catmat"])
        & (pl.col("base") == "sem_outliers")
        & (pl.col("uf") != "BR")
    )
    elig = puf.filter(pl.col("amostra_suficiente")).sort("mediana")
    title = f"{r['nome_curto']}: mediana {fmt.ratio(r['razao'])} maior em {r['uf_max']} do que em {r['uf_min']}"
    sub = (
        f"Preço mediano por unidade nas UFs com amostra suficiente (≥ 5 compras e ≥ 2 órgãos), {ctx.period}. "
        f"IC 95% da razão: {fmt.ratio(r['ic_inf'])} a {fmt.ratio(r['ic_sup'])}."
    )
    fig, top = new_fig(ctx, title, sub)
    ax = fig.add_axes([0.14, 0.25, 0.8, top - 0.27])
    colors = [
        theme.ACCENT if u == r["uf_max"] else theme.LOW if u == r["uf_min"] else theme.PRIMARY
        for u in elig["uf"]
    ]
    bars = ax.barh(elig["uf"].to_list(), elig["mediana"].to_list(), color=colors, height=0.62)
    for b, (med, n) in zip(bars, zip(elig["mediana"], elig["n_compras"], strict=True), strict=True):
        ax.text(
            b.get_width(),
            b.get_y() + b.get_height() / 2,
            f"  {fmt.brl(med, 0)}  (n = {n})",
            va="center",
            fontsize=13,
            color=theme.INK,
        )
    ax.set_xlim(0, elig["mediana"].max() * 1.5)
    ax.xaxis.set_major_locator(MaxNLocator(4))
    ax.xaxis.set_major_formatter(brl_axis())
    ax.tick_params(axis="x", labelsize=12)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", labelsize=15)
    ax.set_xlabel(f"R$ de {ctx.ref} por unidade (n = compras)", fontsize=12, color=theme.MUTED)
    insuf = puf.filter(~pl.col("amostra_suficiente")).height
    fig.text(
        0.06,
        0.16,
        f"{insuf} UF(s) com compras mas amostra insuficiente ficaram de fora. CATMAT {r['codigo_catmat']}.",
        fontsize=11,
        color=theme.MUTED,
    )
    badge(fig, r["robustez"])
    return save(fig, out / "1_ranking_ufs.png")


# ----------------------------------------------- 2. mesmo item, 2 UFs extremas ----
def chart_same_item(ctx: Ctx, out: Path) -> Path | None:
    r = pick_dispersion_item(ctx.t("dispersao_item"))
    if r is None:
        return None
    comp = ctx.t("compras_detalhe").filter(
        (pl.col("codigo_catmat") == r["codigo_catmat"])
        & pl.col("no_periodo")
        & ~pl.col("outlier")
        & pl.col("uf").is_in([r["uf_max"], r["uf_min"]])
    )
    title = f"Mesmo item, preços diferentes: {fmt.brl(r['mediana_max'], 0)} em {r['uf_max']} × {fmt.brl(r['mediana_min'], 0)} em {r['uf_min']}"
    sub = f"{r['nome_curto']} (CATMAT {r['codigo_catmat']}). Cada ponto é um registro de compra, {ctx.period}; a linha é a mediana."
    fig, top = new_fig(ctx, title, sub)
    ax = fig.add_axes([0.16, 0.25, 0.78, top - 0.27])
    rng = np.random.default_rng(7)
    for i, (uf, color, n, org) in enumerate(
        [
            (r["uf_max"], theme.ACCENT, r["n_compras_max"], r["n_orgaos_max"]),
            (r["uf_min"], theme.LOW, r["n_compras_min"], r["n_orgaos_min"]),
        ]
    ):
        vals = comp.filter(pl.col("uf") == uf)["preco_real"].to_numpy()
        ax.scatter(
            i + rng.uniform(-0.18, 0.18, vals.size),
            vals,
            s=70,
            color=color,
            alpha=0.75,
            edgecolor="white",
            linewidth=0.8,
            zorder=3,
        )
        med = float(np.median(vals))
        ax.hlines(med, i - 0.32, i + 0.32, color=theme.INK, linewidth=3, zorder=4)
        ax.text(
            i + 0.36,
            med,
            fmt.brl(med, 0),
            va="center",
            fontsize=15,
            fontweight="bold",
            color=theme.INK,
        )
        ax.text(
            i,
            -0.1,
            f"{uf}\n{n} compras · {org} órgãos",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="top",
            fontsize=13,
            color=theme.INK,
        )
    ax.set_xlim(-0.6, 1.9)
    ax.set_xticks([])
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.yaxis.set_major_formatter(brl_axis())
    ax.tick_params(axis="y", labelsize=12)
    ax.set_ylabel(f"R$ de {ctx.ref} por unidade", fontsize=12, color=theme.MUTED)
    ax.set_ylim(0, None)
    fig.text(
        0.06,
        0.15,
        _wrap(
            f"Razão das medianas {fmt.ratio(r['razao'])} (IC 95%: {fmt.ratio(r['ic_inf'])}–{fmt.ratio(r['ic_sup'])}). {r['motivo_robustez'][:1].upper() + r['motivo_robustez'][1:]}.",
            100,
        ),
        fontsize=10.5,
        color=theme.MUTED,
        va="center",
    )
    badge(fig, r["robustez"])
    return save(fig, out / "2_mesmo_item_duas_ufs.png")


# --------------------------------------------- 3. dependência de importação ----
def chart_dependence(ctx: Ctx, out: Path) -> Path | None:
    imp = ctx.t("importacao_ncm_ano")
    if imp.height == 0:
        return None
    full = imp.filter(
        (pl.col("meses_com_dados") == 12) & ~pl.col("ncm_historico") & pl.col("ncm_especifico")
    )
    year = int(full["ano"].max())
    fam = (
        full.filter(pl.col("ano") == year)
        .group_by("familia_macro", maintain_order=True)
        .agg(pl.col("fob_usd").sum(), pl.col("export_fob_usd").sum())
        .with_columns((pl.col("export_fob_usd") / pl.col("fob_usd")).alias("cob"))
        .sort("fob_usd")
    )
    anv = ctx.t("anvisa_registros_familia")
    tot_i, tot_e = fam["fob_usd"].sum(), fam["export_fob_usd"].sum()
    low = fam.filter(pl.col("cob") < 0.1)
    title = f"Em {year}, o Brasil importou {fmt.usd_compact(tot_i)} em OPME e exportou {fmt.usd_compact(tot_e)}"
    sub = f"Valores FOB por família (NCMs específicos). Em {low.height} de {fam.height} famílias, a exportação não chega a 10% da importação."
    fig, top = new_fig(ctx, title, sub, extra_source="Registros: ANVISA.")
    ax = fig.add_axes([0.38, 0.22, 0.56, top - 0.24])
    y = np.arange(fam.height)
    ax.barh(y + 0.2, fam["fob_usd"] / 1e6, height=0.38, color=theme.ACCENT, label="Importação")
    ax.barh(y - 0.2, fam["export_fob_usd"] / 1e6, height=0.38, color=theme.LOW, label="Exportação")
    labels = []
    for rr in fam.iter_rows(named=True):
        a = (
            anv.filter(pl.col("familia_macro") == rr["familia_macro"])
            if anv.height
            else pl.DataFrame()
        )
        extra = (
            f"\n{fmt.pct(a['share_so_estrangeiro'][0], 0)} dos registros ANVISA\nsó c/ fabricante estrangeiro"
            if a.height
            else ""
        )
        labels.append(rr["familia_macro"] + extra)
        ax.text(
            rr["fob_usd"] / 1e6,
            list(fam["familia_macro"]).index(rr["familia_macro"]) + 0.2,
            f"  {fmt.num(rr['fob_usd'] / 1e6, 0)}",
            va="center",
            fontsize=11.5,
        )
        ax.text(
            rr["export_fob_usd"] / 1e6,
            list(fam["familia_macro"]).index(rr["familia_macro"]) - 0.2,
            f"  {fmt.num(rr['export_fob_usd'] / 1e6, 0)} ({fmt.pct(rr['cob'], 0)})",
            va="center",
            fontsize=11.5,
            color=theme.LOW,
        )
    ax.set_yticks(y, labels, fontsize=10)
    ax.set_xlabel(
        "US$ milhões (FOB); entre parênteses: export. ÷ import.", fontsize=11, color=theme.MUTED
    )
    ax.set_xlim(0, fam["fob_usd"].max() / 1e6 * 1.3)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=False, fontsize=12)
    badge(fig, "forte")
    return save(fig, out / "3_dependencia_importacao.png")


# ------------------------------------------------ 4. ponte importação × público ----
def chart_bridge(ctx: Ctx, out: Path) -> Path | None:
    ponte = ctx.t("ponte_preco_importacao").filter(pl.col("comparavel_por_unidade"))
    if ponte.height == 0:
        return None
    r = ponte.row(0, named=True)
    title = f"{r['familia_macro']}: o setor público paga {fmt.ratio(r['razao_publico_importacao'])} o preço de importação"
    sub = (
        f"Preço CIF médio por unidade importada ({r['anos_importacao']}, NCM {r['ncms']}) × mediana das compras públicas "
        f"({r['n_compras_publico']} compras, {r['periodo_publico']}). R$ de {ctx.ref}."
    )
    fig, top = new_fig(ctx, title, sub)
    ax = fig.add_axes([0.16, 0.5, 0.78, top - 0.52])
    vals = [r["preco_cif_brl_real_unid"], r["preco_publico_mediana"]]
    bars = ax.bar(
        ["Importação (CIF)", "Compra pública\n(mediana)"],
        vals,
        color=[theme.LOW, theme.ACCENT],
        width=0.55,
    )
    for b, v in zip(bars, vals, strict=True):
        ax.text(
            b.get_x() + b.get_width() / 2,
            v,
            fmt.brl(v, 0),
            ha="center",
            va="bottom",
            fontsize=18,
            fontweight="bold",
        )
    ax.yaxis.set_major_locator(MaxNLocator(4))
    ax.yaxis.set_major_formatter(brl_axis())
    ax.tick_params(axis="y", labelsize=12)
    ax.set_ylim(0, max(vals) * 1.25)
    ax.grid(axis="x", visible=False)
    ax.tick_params(axis="x", labelsize=14)
    comps = r["componentes_diferenca"].split("; ")
    fig.text(
        0.06,
        0.425,
        "O que existe entre um preço e outro:",
        fontsize=15,
        fontweight="bold",
        color=theme.INK,
    )
    for i, c in enumerate(comps):
        fig.text(0.08, 0.39 - i * 0.026, "• " + c, fontsize=12, color=theme.INK)
    fig.text(
        0.06,
        0.15,
        _wrap(
            "É contexto, não acusação. Compara agregados diferentes: todo o NCM importado × itens do catálogo comprados pelo setor público.",
            95,
        ),
        fontsize=10.5,
        color=theme.MUTED,
    )
    badge(fig, "moderado", y=0.098)
    return save(fig, out / "4_importacao_vs_publico.png")


# ------------------------------------------------------- 5. evolução real ----
def chart_trend(ctx: Ctx, out: Path) -> Path | None:
    ach = ctx.t("achados").filter(pl.col("tipo") == "tendencia_real")
    if ach.height == 0:
        return None
    # Item-âncora: mais robusto; entre iguais, item homogêneo e IC mais estreito.
    het = ctx.t("dispersao_item").select("codigo_catmat", "item_heterogeneo")
    ach = (
        ach.join(het, on="codigo_catmat", how="left")
        .with_columns(
            pl.col("robustez").replace_strict(ROB_ORDER, return_dtype=pl.Int64).alias("_r"),
            pl.col("numeros").str.json_path_match("$.ic_sup").cast(pl.Float64).alias("_hi"),
            pl.col("numeros").str.json_path_match("$.ic_inf").cast(pl.Float64).alias("_lo"),
        )
        .with_columns(
            ((pl.col("_hi") - pl.col("_lo")) / ((pl.col("_hi") + pl.col("_lo")) / 2)).alias("_w")
        )
        .sort(["_r", "item_heterogeneo", "_w"], descending=[False, False, False], nulls_last=True)
    )
    a = ach.row(0, named=True)
    nums = json.loads(a["numeros"])
    serie = (
        ctx.t("serie_item_mes")
        .filter((pl.col("codigo_catmat") == a["codigo_catmat"]) & pl.col("publicavel"))
        .sort("mes")
    )
    var = nums["variacao"]
    title = f"{a['item']}: preço real {'caiu' if var < 0 else 'subiu'} {fmt.pct(abs(var), 0)}"
    sub = f"Mediana mensal em R$ de {ctx.ref} (IPCA). Comparação: {nums['periodo_inicio']} ({nums['n_inicio']} compras) × {nums['periodo_fim']} ({nums['n_fim']} compras)."
    fig, top = new_fig(ctx, title, sub, extra_source="")
    ax = fig.add_axes([0.16, 0.24, 0.78, top - 0.26])
    x = serie["mes"].to_list()
    ax.plot(
        x,
        serie["mediana_real"],
        "o",
        color=theme.PRIMARY,
        alpha=0.45,
        markersize=6,
        label="Mediana do mês",
    )
    roll = serie["mediana_real"].rolling_median(window_size=6, min_samples=3)
    ax.plot(x, roll, color=theme.PRIMARY, linewidth=3.5, label="Mediana móvel de 6 meses")
    for lbl, val, side in (
        (nums["periodo_inicio"], nums["mediana_inicio"], 0),
        (nums["periodo_fim"], nums["mediana_fim"], 1),
    ):
        ax.axhline(val, color=theme.ACCENT if side else theme.LOW, linestyle="--", linewidth=1.5)
        ax.text(
            x[0] if side == 0 else x[-1],
            val,
            f" {fmt.brl(val, 0)} ({lbl})",
            ha="left" if side == 0 else "right",
            va="bottom",
            fontsize=11.5,
            color=theme.INK,
        )
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ax.yaxis.set_major_formatter(brl_axis())
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.tick_params(labelsize=12)
    ax.set_ylim(0, None)
    ax.legend(loc="lower left", frameon=False, fontsize=11.5)
    fig.text(
        0.06,
        0.155,
        f"IC 95% da razão entre as medianas: {fmt.ratio(nums['ic_inf'], 2)} a {fmt.ratio(nums['ic_sup'], 2)}. CATMAT {a['codigo_catmat']}.",
        fontsize=11,
        color=theme.MUTED,
    )
    badge(fig, a["robustez"])
    return save(fig, out / "5_evolucao_preco_real.png")


# --------------------------------------------- 6. heterogeneidade do catálogo ----
def chart_heterogeneity(ctx: Ctx, out: Path) -> Path | None:
    d = ctx.t("dispersao_item").sort("p90_p10_nacional")
    if d.height == 0:
        return None
    lim = ctx.s.analysis.max_p90_p10_homogeneo
    n_het = d.filter(pl.col("item_heterogeneo")).height
    title = f"Em {n_het} de {d.height} itens, o mesmo código de catálogo esconde preços mais de {fmt.num(lim)}× diferentes"
    sub = f"Razão P90/P10 do preço por unidade no Brasil, por item CATMAT, {ctx.period}, sem outliers. Acima de {fmt.num(lim)}×, comparar UFs mede o mix de marcas, não o preço."
    fig, top = new_fig(ctx, title, sub)
    ax = fig.add_axes([0.5, 0.22, 0.44, top - 0.24])
    colors = [theme.ACCENT if h else theme.PRIMARY for h in d["item_heterogeneo"]]
    ax.barh(
        [textwrap.shorten(n, 46, placeholder="…") for n in d["nome_curto"]],
        d["p90_p10_nacional"],
        color=colors,
        height=0.7,
    )
    ax.axvline(lim, color=theme.INK, linestyle="--", linewidth=1.2)
    ax.set_xscale("log")
    ax.set_xticks([1, 2, 5, 10, 20, 50])
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt.ratio(v, 0)))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.tick_params(axis="x", labelsize=12)
    ax.set_xlim(1, max(60, float(d["p90_p10_nacional"].max()) * 1.2))
    ax.tick_params(axis="y", labelsize=9.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("P90 ÷ P10 (escala log)", fontsize=11, color=theme.MUTED)
    badge(fig, "forte", y=0.1)
    return save(fig, out / "6_heterogeneidade_catalogo.png")


# ------------------------------------------------ 7. Tabela SUS × preço ----
def chart_sigtap(ctx: Ctx, out: Path) -> Path | None:
    """Razão mediana paga ÷ valor SIGTAP, só pares de confiança alta, com IC 95%."""
    ponte = ctx.t("ponte_sigtap_preco")
    if ponte.height == 0:
        return None
    v = ponte.filter(
        (pl.col("confianca") == "alta") & pl.col("razao_preco_sigtap").is_not_null()
    ).sort("razao_preco_sigtap")
    if v.height == 0:
        return None
    above = v.filter(pl.col("ic_inf") > 1)
    below = v.filter(pl.col("ic_sup") < 1)
    comp = v.row(0, named=True)["competencia_sigtap"]
    comp_lbl = f"{comp[4:]}/{comp[:4]}"
    title = f"Tabela SUS × preço pago: {above.height} itens acima, {below.height} abaixo"
    sub = (
        f"Mediana paga por unidade ({ctx.period}, R$ de {ctx.ref}) ÷ reembolso do SUS "
        f"(SIGTAP {comp_lbl}). {v.height} pares de mapeamento com confiança alta."
    )
    fig, top = new_fig(ctx, title, sub, extra_source="Tabela SUS: SIGTAP/DATASUS.")
    ax = fig.add_axes([0.40, 0.275, 0.37, top - 0.295])
    y = np.arange(v.height)
    colors = [
        theme.ACCENT if lo > 1 else theme.LOW if hi < 1 else theme.MUTED
        for lo, hi in zip(v["ic_inf"], v["ic_sup"], strict=True)
    ]
    for i, rr in enumerate(v.iter_rows(named=True)):
        ax.plot([rr["ic_inf"], rr["ic_sup"]], [i, i], color=theme.GRID_DARK, linewidth=3, zorder=2)
        ax.scatter(rr["razao_preco_sigtap"], i, s=150, color=colors[i], zorder=3, edgecolor="white")
        # Valor numa coluna fixa à direita: não cruza a linha de 1× nem os intervalos.
        ax.text(
            1.04,
            i,
            f"{fmt.ratio(rr['razao_preco_sigtap'], 2)}",
            transform=ax.get_yaxis_transform(),
            va="center",
            fontsize=14,
            fontweight="bold",
            color=colors[i],
        )
        ax.text(
            1.33,
            i,
            f"n = {rr['n_compras']}",
            transform=ax.get_yaxis_transform(),
            va="center",
            fontsize=9.5,
            color=theme.MUTED,
        )
    ax.axvline(1, color=theme.INK, linestyle="--", linewidth=1.3)
    ax.set_yticks(y, ["\n".join(textwrap.wrap(n, 30)[:2]) for n in v["nome_curto"]], fontsize=10)
    ax.set_xscale("log")
    lo_lim = min(0.2, float(v["ic_inf"].min()) * 0.8)
    ax.set_xlim(lo_lim, max(3.0, float(v["ic_sup"].max()) * 1.4))
    ticks = [t for t in (0.25, 0.5, 1, 2) if lo_lim <= t]
    ax.set_xticks(ticks)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda val, _: fmt.ratio(val, 2 if val < 1 else 0)))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.tick_params(axis="x", labelsize=11.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Mediana paga ÷ Tabela SUS (log; traço = IC 95%)", fontsize=11, color=theme.MUTED)
    fig.text(
        0.06,
        0.165,
        _wrap(
            "O SIGTAP é reembolso do SUS ao hospital, não preço de compra. Acima de 1×, indica "
            "defasagem da tabela, não conduta de quem compra.",
            84,
        ),
        fontsize=10.5,
        color=theme.MUTED,
        va="center",
    )
    ach = ctx.t("achados").filter(pl.col("tipo") == "ponte_sigtap")
    rob = min(ach["robustez"].to_list(), key=lambda x: ROB_ORDER[x]) if ach.height else "moderado"
    badge(fig, rob)
    return save(fig, out / "7_tabela_sus_vs_preco.png")


# ------------------------------------------------------------ carrossel ----
def _text_page(
    ctx: Ctx, title: str, body: list[str], kicker: str = "", big: str = "", big_caption: str = ""
) -> plt.Figure:
    plt.rcParams.update(theme.mpl_rc())
    fig = plt.figure(figsize=(ctx.w, ctx.h), dpi=ctx.dpi)
    fig.patch.set_facecolor(theme.PAGE_BG)
    fig.add_artist(
        plt.Rectangle((0, 0.975), 1, 0.025, transform=fig.transFigure, color=theme.PRIMARY)
    )
    y = 0.9
    if kicker:
        fig.text(0.08, y, kicker.upper(), fontsize=15, color=theme.PRIMARY, fontweight="bold")
        y -= 0.05
    t_lines = textwrap.wrap(title, 19)
    fig.text(
        0.08,
        y,
        "\n".join(t_lines),
        fontsize=40,
        fontweight="bold",
        color=theme.DARK,
        va="top",
        linespacing=1.1,
    )
    y -= 0.068 * len(t_lines) + 0.04
    if big:
        fig.text(0.08, y, big, fontsize=80, fontweight="bold", color=theme.ACCENT, va="top")
        y -= 0.115
        if big_caption:
            fig.text(0.08, y, _wrap(big_caption, 40), fontsize=19, color=theme.MUTED, va="top")
            y -= 0.035 * len(textwrap.wrap(big_caption, 40)) + 0.035
    for para in body:
        lines = textwrap.wrap(para, 40)
        fig.text(
            0.08, y, "\n".join(lines), fontsize=20, color=theme.INK, va="top", linespacing=1.35
        )
        y -= 0.039 * len(lines) + 0.032
    fig.text(
        0.08,
        0.04,
        "Raio-X OPME · " + ctx.url.removeprefix("https://"),
        fontsize=12,
        color=theme.PRIMARY,
    )
    return fig


def build_carousel(ctx: Ctx, charts: list[Path], out: Path) -> Path:
    from matplotlib.image import imread

    ach = ctx.t("achados")
    m = ctx.meta
    fortes = ach.filter(pl.col("robustez") == "forte")
    pages = [
        _text_page(
            ctx,
            "Quanto o setor público paga por stents, próteses e implantes?",
            [
                "Mais a importação desses itens de 2015 a hoje. O que os dados mostram, e o que eles não permitem afirmar.",
            ],
            kicker="Raio-X OPME",
            big=fmt.num(m["n_compras_periodo"]),
            big_caption=f"compras públicas de {m['n_itens']} itens OPME em {m['n_ufs_periodo']} UFs ({m['periodo_label']})",
        ),
        _text_page(
            ctx,
            "O problema",
            [
                "OPME (órteses, próteses e materiais especiais) é um dos itens mais caros e menos transparentes da saúde.",
                "A pergunta clássica é: o mesmo item custa mais caro em alguns estados?",
                "Para responder com honestidade, só comparei o mesmo código de catálogo, na mesma unidade, com amostra mínima e intervalo de confiança.",
            ],
            kicker="Contexto",
        ),
    ]
    for p in charts:
        fig = plt.figure(figsize=(ctx.w, ctx.h), dpi=ctx.dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.imshow(imread(p))
        ax.axis("off")
        pages.append(fig)
    pages.append(
        _text_page(
            ctx,
            "Metodologia em uma página",
            [
                "Fonte: API de Dados Abertos do Compras.gov.br (preços praticados), ComexStat, BCB (IPCA e câmbio), IBGE e ANVISA.",
                f"Comparação só do mesmo CATMAT e unidade. UF entra com ≥ {m['regras']['min_compras_uf']} compras e ≥ {m['regras']['min_orgaos_uf']} órgãos.",
                f"Mediana, nunca média. Valores em R$ de {ctx.ref} (IPCA). Outliers marcados e excluídos.",
                f"Razão entre UFs com IC por bootstrap ({fmt.num(m['regras']['bootstrap_reps'])} reamostragens). Achado forte só se IC inferior > {fmt.num(m['regras']['ic_inferior_minimo'], 1)}.",
            ],
            kicker="Como fiz",
        )
    )
    pages.append(
        _text_page(
            ctx,
            "Limitações",
            [
                "A base cobre órgãos que usam o Compras.gov.br; não é o universo das compras públicas.",
                "O mesmo código de catálogo pode abrigar marcas e especificações diferentes.",
                "Diferença de preço tem causas legítimas: volume, prazo, logística, consignação, urgência.",
                f"Nenhuma diferença entre UFs passou em todas as regras para ser chamada de forte ({fortes.filter(pl.col('tipo') == 'dispersao_uf').height} achados fortes desse tipo).",
            ],
            kicker="Leia antes de compartilhar",
        )
    )
    pages.append(
        _text_page(
            ctx,
            "Código e dados abertos",
            [
                f"Painel interativo: {ctx.url}",
                f"Repositório (MIT): {ctx.s.project.repo_url}",
                "Tudo reproduzível com 4 comandos. Críticas e sugestões são bem-vindas.",
            ],
            kicker="Explore",
        )
    )
    path = out / "raio-x-opme.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(
        path,
        metadata={
            "Title": "Raio-X OPME",
            "Author": "Gabriel Cunha",
            "CreationDate": None,
            "ModDate": None,
        },
    ) as pdf:
        for fig in pages:
            pdf.savefig(fig, dpi=ctx.dpi)
            plt.close(fig)
    logger.info("Carrossel: {} páginas → {}", len(pages), path.name)
    return path


def build_all(settings: Settings) -> list[Path]:
    ctx = Ctx(settings)
    base = settings.path("linkedin")
    out_png = base / "graficos"
    paths = []
    for fn in (
        chart_ranking,
        chart_same_item,
        chart_dependence,
        chart_bridge,
        chart_trend,
        chart_heterogeneity,
        chart_sigtap,
    ):
        try:
            p = fn(ctx, out_png)
        except Exception as exc:  # noqa: BLE001 — um gráfico não derruba os outros
            logger.exception("Gráfico {} falhou: {!r}", fn.__name__, exc)
            p = None
        if p:
            paths.append(p)
            logger.info("Gráfico: {}", p.name)
    carousel_charts = [p for p in paths if not p.name.startswith("2_")][:5]
    build_carousel(ctx, carousel_charts, base / "carrossel")
    return paths
