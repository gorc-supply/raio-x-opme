"""Gerador de achados (seção 5.7): frases prontas, com números, n, período, fonte
e nível de robustez (forte / moderado / fraco). Só "forte" vai para post.

Linguagem (seção 9): "variação", "diferença", "dispersão", "indício que merece
investigação". Nunca termos acusatórios — `schemas.check_language` barra isso.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import numpy as np
import polars as pl

from raiox import fmt
from raiox.analytics.dispersion import Period, _add_months, _cluster_bootstrap_median
from raiox.config import Settings
from raiox.logs import logger

FONTE_PRECOS = "Compras.gov.br (API de Dados Abertos, pesquisa de preços)"
FONTE_COMEX = "ComexStat/MDIC"
WEIGHT = {"forte": 3, "moderado": 2, "fraco": 1}


def _round(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 6)
    return v


def _finding(**kw: Any) -> dict[str, Any]:
    nums = {k: _round(v) for k, v in kw.get("numeros", {}).items()}
    kw["numeros"] = json.dumps(nums, ensure_ascii=False, default=str)
    kw.setdefault("codigo_catmat", None)
    kw.setdefault("item", None)
    kw.setdefault("familia", None)
    kw["score"] = WEIGHT[kw["robustez"]] * 100 + float(kw.pop("_magnitude", 0))
    return kw


# ------------------------------------------------------------ dispersão UF ----
def _dispersion_findings(disp: pl.DataFrame, mes_ref: str) -> list[dict]:
    out = []
    for r in disp.filter(pl.col("robustez") != "sem_comparacao").iter_rows(named=True):
        frase = (
            f"O mesmo item ({r['nome_curto']}, CATMAT {r['codigo_catmat']}) teve preço mediano de "
            f"{fmt.brl(r['mediana_max'])} em {r['uf_max']} e {fmt.brl(r['mediana_min'])} em {r['uf_min']}: "
            f"{fmt.ratio(r['razao'])} de diferença (IC 95%: {fmt.ratio(r['ic_inf'])} a {fmt.ratio(r['ic_sup'])}). "
            f"Base: {r['n_compras_max']} compras em {r['uf_max']} e {r['n_compras_min']} em {r['uf_min']}, "
            f"de {r['periodo_inicio']:%m/%Y} a {r['periodo_fim']:%m/%Y}, R$ de {mes_ref}, por unidade."
        )
        out.append(
            _finding(
                id=f"disp_uf_{r['codigo_catmat']}",
                tipo="dispersao_uf",
                codigo_catmat=r["codigo_catmat"],
                item=r["nome_curto"],
                familia=r["familia"],
                titulo=f"{r['nome_curto']}: {fmt.ratio(r['razao'])} entre {r['uf_max']} e {r['uf_min']}",
                frase=frase,
                numeros={
                    "uf_max": r["uf_max"],
                    "mediana_max": r["mediana_max"],
                    "n_compras_max": r["n_compras_max"],
                    "n_orgaos_max": r["n_orgaos_max"],
                    "uf_min": r["uf_min"],
                    "mediana_min": r["mediana_min"],
                    "n_compras_min": r["n_compras_min"],
                    "n_orgaos_min": r["n_orgaos_min"],
                    "razao": r["razao"],
                    "ic_inf": r["ic_inf"],
                    "ic_sup": r["ic_sup"],
                    "n_ufs_elegiveis": r["n_ufs_elegiveis"],
                },
                n=int(r["n_compras_max"] + r["n_compras_min"]),
                n_descricao=f"{r['n_compras_max']} compras em {r['uf_max']}; {r['n_compras_min']} em {r['uf_min']}",
                periodo=f"{r['periodo_inicio']:%m/%Y} a {r['periodo_fim']:%m/%Y}",
                unidade="R$ por unidade",
                fonte=FONTE_PRECOS,
                robustez=r["robustez"],
                motivo_robustez=r["motivo_robustez"],
                _magnitude=min(r["ic_inf"] or 0, 10) * 10,
            )
        )
    return out


# ------------------------------------------------------ dispersão nacional ----
def _national_findings(puf: pl.DataFrame, s: Settings, mes_ref: str) -> list[dict]:
    fc = s.findings
    out = []
    nat = puf.filter((pl.col("uf") == "BR") & (pl.col("base") == "sem_outliers"))
    for r in nat.iter_rows(named=True):
        ratio = r["p90"] / r["p10"]
        if ratio < fc.p90_p10_minimo:
            continue
        rob = (
            "forte"
            if r["n_compras"] >= fc.min_compras_forte
            else ("moderado" if r["n_compras"] >= fc.min_compras_moderado else "fraco")
        )
        hetero = ratio > s.analysis.max_p90_p10_homogeneo
        base_txt = (
            f"Base: {r['n_compras']} compras de {r['n_orgaos']} órgãos, "
            f"{r['periodo_inicio']:%m/%Y} a {r['periodo_fim']:%m/%Y}, R$ de {mes_ref}, sem outliers."
        )
        if hetero:
            titulo = f"{r['nome_curto']}: mesmo código CATMAT, preços {fmt.ratio(ratio)} diferentes (P90/P10)"
            frase = (
                f"Sob o mesmo código CATMAT {r['codigo_catmat']} ({r['nome_curto']}), os 10% mais caros pagaram ao menos "
                f"{fmt.brl(r['p90'])} por unidade e os 10% mais baratos até {fmt.brl(r['p10'])}: {fmt.ratio(ratio)} de dispersão. "
                "O código abriga marcas e especificações diferentes, o que limita a comparação direta de preços. "
                + base_txt
            )
        else:
            titulo = f"{r['nome_curto']}: P90/P10 de {fmt.ratio(ratio)} no Brasil"
            frase = (
                f"Dentro do país, os 10% mais caros entre as compras de {r['nome_curto']} pagaram ao menos "
                f"{fmt.brl(r['p90'])} por unidade, enquanto os 10% mais baratos pagaram até {fmt.brl(r['p10'])}: "
                f"uma dispersão de {fmt.ratio(ratio)} (P90/P10). " + base_txt
            )
        out.append(
            _finding(
                id=f"disp_br_{r['codigo_catmat']}",
                tipo="dispersao_nacional",
                codigo_catmat=r["codigo_catmat"],
                item=r["nome_curto"],
                familia=r["familia"],
                titulo=titulo,
                frase=frase,
                numeros={
                    "p10": r["p10"],
                    "p90": r["p90"],
                    "mediana": r["mediana"],
                    "p90_p10": ratio,
                    "n_compras": r["n_compras"],
                    "n_orgaos": r["n_orgaos"],
                    "item_heterogeneo": hetero,
                },
                n=int(r["n_compras"]),
                n_descricao=f"{r['n_compras']} compras, {r['n_orgaos']} órgãos",
                periodo=f"{r['periodo_inicio']:%m/%Y} a {r['periodo_fim']:%m/%Y}",
                unidade="R$ por unidade",
                fonte=FONTE_PRECOS,
                robustez=rob,
                motivo_robustez=f"estatística descritiva com {r['n_compras']} compras (forte exige ≥ {fc.min_compras_forte})",
                _magnitude=min(ratio, 10) * 5,
            )
        )
    return out


# ---------------------------------------------------------------- tendência ----
def _trend_findings(comp: pl.DataFrame, s: Settings, mes_ref: str, period: Period) -> list[dict]:
    fc, cfg = s.findings, s.analysis
    rng = np.random.default_rng(cfg.bootstrap_seed + 1)
    alpha = (1 - cfg.ci_level) / 2
    win = fc.janela_tendencia_meses
    end = period.end
    base = comp.filter(
        ~pl.col("outlier") & pl.col("preco_real").is_not_null() & (pl.col("mes") <= end)
    )
    out = []
    for (code, name, fam), g in base.group_by(
        ["codigo_catmat", "nome_curto", "familia"], maintain_order=True
    ):
        first = g["mes"].min()
        a_end = _add_months(first, win - 1)  # janela inicial: N meses a partir da 1ª compra
        b_start = _add_months(end, -(win - 1))
        if a_end >= b_start:
            continue
        a = g.filter(pl.col("mes") <= a_end)
        b = g.filter(pl.col("mes") >= b_start)
        na, nb = a["id_compra"].n_unique(), b["id_compra"].n_unique()
        if min(na, nb) < fc.min_compras_moderado:
            continue
        ma, mb = float(a["preco_real"].median()), float(b["preco_real"].median())
        ba = _cluster_bootstrap_median(
            a["preco_real"].to_numpy(), a["id_compra"].to_numpy(), cfg.bootstrap_reps, rng
        )
        bb = _cluster_bootstrap_median(
            b["preco_real"].to_numpy(), b["id_compra"].to_numpy(), cfg.bootstrap_reps, rng
        )
        lo, hi = np.quantile(bb / ba, [alpha, 1 - alpha])
        change = mb / ma - 1
        clear = hi < 1 - fc.tendencia_margem or lo > 1 + fc.tendencia_margem
        if clear and min(na, nb) >= fc.min_compras_forte:
            rob = "forte"
        elif hi < 1 or lo > 1:
            rob = "moderado"
        else:
            rob = "fraco"
        verbo = "caiu" if change < 0 else "subiu"
        pa = f"{first:%m/%Y} a {a_end:%m/%Y}"
        pb = f"{b_start:%m/%Y} a {end:%m/%Y}"
        frase = (
            f"Em reais de {mes_ref}, o preço mediano de {name} {verbo} {fmt.pct(abs(change))}: "
            f"de {fmt.brl(ma)} ({pa}, {na} compras) para {fmt.brl(mb)} ({pb}, {nb} compras). "
            f"IC 95% da razão: {fmt.ratio(lo, 2)} a {fmt.ratio(hi, 2)}."
        )
        out.append(
            _finding(
                id=f"tend_{code}",
                tipo="tendencia_real",
                codigo_catmat=code,
                item=name,
                familia=fam,
                titulo=f"{name}: preço real {verbo} {fmt.pct(abs(change), 0)}",
                frase=frase,
                numeros={
                    "mediana_inicio": ma,
                    "mediana_fim": mb,
                    "variacao": change,
                    "ic_inf": lo,
                    "ic_sup": hi,
                    "n_inicio": na,
                    "n_fim": nb,
                    "periodo_inicio": pa,
                    "periodo_fim": pb,
                },
                n=int(na + nb),
                n_descricao=f"{na} compras no início; {nb} no fim",
                periodo=f"{pa} vs. {pb}",
                unidade="R$ por unidade (reais)",
                fonte=FONTE_PRECOS + "; IPCA/BCB",
                robustez=rob,
                motivo_robustez=f"IC da razão {fmt.num(lo, 2)}–{fmt.num(hi, 2)}; forte exige IC fora de ±{fmt.pct(fc.tendencia_margem, 0)} e ≥ {fc.min_compras_forte} compras em cada janela",
                _magnitude=min(abs(change), 1) * 50,
            )
        )
    return out


# ------------------------------------------------------------- concentração ----
def _concentration_findings(forn: pl.DataFrame, s: Settings, period: Period) -> list[dict]:
    fc = s.findings
    top = s.analysis.top_n_concentration
    out = []
    f = forn.filter(pl.col("tipo") == "fornecedor")
    for (code, name, fam), g in f.group_by(
        ["codigo_catmat", "nome_curto", "familia"], maintain_order=True
    ):
        cr = float(g[f"cr{top}"][0])
        hhi = float(g["hhi"][0])
        n = int(g["n_compras"].sum())
        if cr < fc.cr3_minimo:
            continue
        rob = (
            "forte"
            if n >= fc.min_compras_forte
            else ("moderado" if n >= fc.min_compras_moderado else "fraco")
        )
        frase = (
            f"Os {top} maiores fornecedores responderam por {fmt.pct(cr, 0)} do valor comprado de {name} "
            f"({g.height} fornecedores no total; HHI {fmt.num(hhi)}), de {period.label}. "
            "Concentração alta não indica irregularidade: pode refletir poucos fabricantes com registro no país."
        )
        out.append(
            _finding(
                id=f"conc_{code}",
                tipo="concentracao_fornecedores",
                codigo_catmat=code,
                item=name,
                familia=fam,
                titulo=f"{name}: {top} fornecedores = {fmt.pct(cr, 0)} do valor",
                frase=frase,
                numeros={f"cr{top}": cr, "hhi": hhi, "n_fornecedores": g.height},
                n=n,
                n_descricao=f"{n} registros-compra, {g.height} fornecedores",
                periodo=period.label,
                unidade="% do valor em R$",
                fonte=FONTE_PRECOS,
                robustez=rob,
                motivo_robustez=f"base de {n} compras (forte exige ≥ {fc.min_compras_forte})",
                _magnitude=cr * 20,
            )
        )
    return out


# ---------------------------------------------------------------- importação ----
def _import_findings(imp: pl.DataFrame, ponte: pl.DataFrame | None, mes_ref: str) -> list[dict]:
    out = []
    full = imp.filter(
        (pl.col("meses_com_dados") == 12)
        & ~pl.col("ncm_historico").fill_null(False)
        & pl.col("ncm_especifico").fill_null(True)  # códigos amplos/residuais ficam fora
    )
    if full.height == 0:
        return out
    year = int(full["ano"].max())
    fam = (
        full.filter(pl.col("ano") == year)
        .group_by("familia_macro", maintain_order=True)
        .agg(
            pl.col("fob_usd").sum(),
            pl.col("export_fob_usd").sum(),
            pl.col("ncm").sort().str.join(", ").alias("ncms"),
        )
        .with_columns((pl.col("export_fob_usd") / pl.col("fob_usd")).alias("cobertura"))
        .sort("fob_usd", descending=True)
    )
    for r in fam.iter_rows(named=True):
        if r["fob_usd"] < 1e6:
            continue
        frase = (
            f"Em {year}, o Brasil importou {fmt.usd_compact(r['fob_usd'])} (FOB) em {r['familia_macro'].lower()} "
            f"(NCM {r['ncms']}) e exportou {fmt.usd_compact(r['export_fob_usd'])}: as exportações cobriram "
            f"{fmt.pct(r['cobertura'])} das importações."
        )
        out.append(
            _finding(
                id=f"imp_{r['familia_macro']}",
                tipo="dependencia_importacao",
                familia=r["familia_macro"],
                titulo=f"{r['familia_macro']}: exportação cobre {fmt.pct(r['cobertura'], 0)} da importação",
                frase=frase,
                numeros={
                    "ano": year,
                    "import_fob_usd": r["fob_usd"],
                    "export_fob_usd": r["export_fob_usd"],
                    "cobertura": r["cobertura"],
                    "ncms": r["ncms"],
                },
                n=0,
                n_descricao="registro censitário do comércio exterior (sem amostragem)",
                periodo=str(year),
                unidade="US$ FOB",
                fonte=FONTE_COMEX,
                robustez="forte",
                motivo_robustez="dado censitário oficial; não depende de amostra",
                _magnitude=(1 - min(r["cobertura"], 1)) * 30,
            )
        )
    # País principal por NCM específico.
    for r in (
        full.filter(pl.col("ano") == year).sort("fob_usd", descending=True).iter_rows(named=True)
    ):
        if r["fob_usd"] < 5e6 or (r["share_pais_principal"] or 0) < 0.3:
            continue
        frase = (
            f"Em {year}, {fmt.pct(r['share_pais_principal'], 0)} do valor importado em {r['descricao_ncm'].lower()} "
            f"(NCM {r['ncm']}, {fmt.usd_compact(r['fob_usd'])} FOB) teve como origem {r['pais_principal']}. "
            f"Principais origens: {r['top_paises']}."
        )
        out.append(
            _finding(
                id=f"orig_{r['ncm']}",
                tipo="origem_importacao",
                familia=r["familia_macro"],
                titulo=f"NCM {r['ncm']}: {fmt.pct(r['share_pais_principal'], 0)} do valor importado veio de um só país ({r['pais_principal']})",
                frase=frase,
                numeros={
                    "ano": year,
                    "pais": r["pais_principal"],
                    "share": r["share_pais_principal"],
                    "hhi_origem": r["hhi_origem"],
                    "fob_usd": r["fob_usd"],
                },
                n=0,
                n_descricao="registro censitário do comércio exterior",
                periodo=str(year),
                unidade="% do US$ FOB",
                fonte=FONTE_COMEX,
                robustez="forte",
                motivo_robustez="dado censitário oficial",
                _magnitude=r["share_pais_principal"] * 20,
            )
        )
    if ponte is not None:
        for r in ponte.filter(pl.col("comparavel_por_unidade")).iter_rows(named=True):
            frase = (
                f"{r['familia_macro']}: o preço CIF médio de importação foi {fmt.brl(r['preco_cif_brl_real_unid'])} por unidade "
                f"({r['anos_importacao']}, NCM {r['ncms']}), e a mediana paga pelo setor público foi "
                f"{fmt.brl(r['preco_publico_mediana'])} ({r['n_compras_publico']} compras, {r['periodo_publico']}), "
                f"ambos em R$ de {mes_ref}. A diferença ({fmt.ratio(r['razao_publico_importacao'])}) inclui tributos, logística, "
                "registro sanitário, consignação, instrumental, suporte técnico em sala, margem e prazo de pagamento do setor público: é contexto, não indica irregularidade."
            )
            out.append(
                _finding(
                    id=f"ponte_{r['familia_macro']}",
                    tipo="ponte_importacao",
                    familia=r["familia_macro"],
                    titulo=f"{r['familia_macro']}: preço público = {fmt.ratio(r['razao_publico_importacao'])} o CIF de importação",
                    frase=frase,
                    numeros={
                        k: r[k]
                        for k in (
                            "preco_cif_brl_real_unid",
                            "preco_publico_mediana",
                            "razao_publico_importacao",
                            "n_compras_publico",
                            "importacao_qtd_unidades",
                        )
                    },
                    n=int(r["n_compras_publico"]),
                    n_descricao=f"{r['n_compras_publico']} compras públicas; {fmt.num(r['importacao_qtd_unidades'])} unidades importadas",
                    periodo=f"importação {r['anos_importacao']}; compras {r['periodo_publico']}",
                    unidade="R$ por unidade (reais)",
                    fonte=f"{FONTE_COMEX}; {FONTE_PRECOS}; BCB",
                    robustez="moderado",
                    motivo_robustez="compara agregados diferentes (todo o NCM vs. itens do catálogo); serve como contexto",
                    _magnitude=10,
                )
            )
    return out


# ------------------------------------------------------------------- ANVISA ----
def _anvisa_findings(anv: pl.DataFrame, snapshot: str) -> list[dict]:
    out = []
    for r in anv.iter_rows(named=True):
        if r["registros_vigentes"] < 10:
            continue
        frase = (
            f"{r['familia_macro']}: {fmt.pct(r['share_so_estrangeiro'], 0)} dos {r['registros_vigentes']} registros vigentes na ANVISA "
            f"têm apenas fabricante(s) estrangeiro(s). Principais países fabricantes: {r['principais_paises_fabricantes']}. "
            f"Registro não mede volume vendido: é um indicador de dependência tecnológica (dados de {snapshot})."
        )
        out.append(
            _finding(
                id=f"anvisa_{r['familia_macro']}",
                tipo="registros_anvisa",
                familia=r["familia_macro"],
                titulo=f"{r['familia_macro']}: {fmt.pct(r['share_so_estrangeiro'], 0)} dos registros só com fabricante estrangeiro",
                frase=frase,
                numeros={
                    "registros_vigentes": r["registros_vigentes"],
                    "share_so_estrangeiro": r["share_so_estrangeiro"],
                    "share_com_fabricante_nacional": r["share_com_fabricante_nacional"],
                },
                n=int(r["registros_vigentes"]),
                n_descricao=f"{r['registros_vigentes']} registros vigentes",
                periodo=f"registros vigentes em {snapshot}",
                unidade="% dos registros",
                fonte="ANVISA (dados abertos, produtos para saúde)",
                robustez="forte",
                motivo_robustez="base censitária de registros; é proxy, não mede volume",
                _magnitude=r["share_so_estrangeiro"] * 20,
            )
        )
    return out


# ------------------------------------------------------------ Tabela SUS ----
FONTE_SIGTAP = "SIGTAP/DATASUS (Tabela Unificada do SUS)"
SIGTAP_BASE = "O SIGTAP é o valor que o SUS reembolsa ao prestador, não o preço de compra"


def sigtap_note(lo: float, hi: float) -> str:
    """Leitura da razão preço ÷ tabela conforme o IC: acima, abaixo ou em linha com a tabela."""
    if lo > 1:
        return f"{SIGTAP_BASE}: preço acima da tabela indica defasagem do valor de tabela, não conduta de quem compra."
    if hi < 1:
        return f"{SIGTAP_BASE}: aqui o valor de tabela cobre a mediana paga na compra."
    return f"{SIGTAP_BASE}: aqui a mediana paga está em linha com o valor de tabela."


def _sigtap_findings(ponte: pl.DataFrame, s: Settings, mes_ref: str) -> list[dict]:
    """Só pares de confiança ALTA viram achado. Sem validação do mapa, no máximo moderado."""
    fc = s.findings
    m = fc.tendencia_margem
    alta = ponte.filter(
        (pl.col("confianca") == "alta") & pl.col("razao_preco_sigtap").is_not_null()
    )
    out = []
    for r in alta.iter_rows(named=True):
        n, lo, hi = r["n_compras"], r["ic_inf"], r["ic_sup"]
        clear = lo > 1 + m or hi < 1 - m
        if clear and n >= fc.min_compras_forte:
            rob = "forte"
        elif (lo > 1 or hi < 1) and n >= fc.min_compras_moderado:
            rob = "moderado"
        else:
            rob = "fraco"
        motivo = (
            f"{n} compras; IC 95% da razão {fmt.num(lo, 2)}–{fmt.num(hi, 2)} "
            f"(forte exige ≥ {fc.min_compras_forte} compras e IC fora de ±{fmt.pct(m, 0)})"
        )
        if not r["mapa_validado"] and rob == "forte":
            rob = "moderado"
            motivo += "; mapa SIGTAP×CATMAT ainda não validado (config/mapa_sigtap_catmat.yaml)"
        mudou = (
            f" O valor de tabela mudou durante o período (era {fmt.brl(r['valor_sigtap_inicio_periodo'])} "
            f"na competência {r['competencia_inicio_periodo'][4:]}/{r['competencia_inicio_periodo'][:4]})."
            if r["sigtap_mudou_no_periodo"]
            else ""
        )
        comp_lbl = f"{r['competencia_sigtap'][4:]}/{r['competencia_sigtap'][:4]}"
        frase = (
            f"{r['nome_curto']} (CATMAT {r['codigo_catmat']}): mediana de {fmt.brl(r['mediana_preco_real'])} "
            f"por unidade nas compras públicas ({n} compras de {r['n_orgaos']} órgãos, "
            f"{r['periodo_inicio']:%m/%Y} a {r['periodo_fim']:%m/%Y}, R$ de {mes_ref}), contra "
            f"{fmt.brl(r['valor_sigtap_nominal'])} na Tabela SUS (SIGTAP {r['codigo_sigtap_fmt']}, "
            f"competência {comp_lbl}): o preço praticado é {fmt.ratio(r['razao_preco_sigtap'])} o valor de "
            f"tabela (IC 95%: {fmt.ratio(lo)} a {fmt.ratio(hi)}).{mudou} {sigtap_note(lo, hi)}"
        )
        out.append(
            _finding(
                id=f"sigtap_{r['codigo_sigtap']}_{r['codigo_catmat']}",
                tipo="ponte_sigtap",
                codigo_catmat=r["codigo_catmat"],
                item=r["nome_curto"],
                familia=r["familia"],
                titulo=f"{r['nome_curto']}: preço praticado = {fmt.ratio(r['razao_preco_sigtap'])} a Tabela SUS",
                frase=frase,
                numeros={
                    "codigo_sigtap": r["codigo_sigtap"],
                    "valor_sigtap": r["valor_sigtap_nominal"],
                    "mediana_preco": r["mediana_preco_real"],
                    "razao": r["razao_preco_sigtap"],
                    "ic_inf": lo,
                    "ic_sup": hi,
                    "n_compras": n,
                    "n_orgaos": r["n_orgaos"],
                    "mapa_validado": r["mapa_validado"],
                },
                n=int(n),
                n_descricao=f"{n} compras, {r['n_orgaos']} órgãos",
                periodo=f"{r['periodo_inicio']:%m/%Y} a {r['periodo_fim']:%m/%Y}; SIGTAP {comp_lbl}",
                unidade="R$ por unidade",
                fonte=f"{FONTE_PRECOS}; {FONTE_SIGTAP}; IPCA/BCB",
                robustez=rob,
                motivo_robustez=motivo,
                _magnitude=min(r["razao_preco_sigtap"], 10) * 3,
            )
        )
    # Defasagem real do valor de tabela (só códigos SIGTAP de pares de confiança alta).
    codes = (
        ponte.filter(
            (pl.col("confianca") == "alta") & pl.col("valor_sigtap_mais_antigo_real").is_not_null()
        )
        .unique(subset="codigo_sigtap", keep="first", maintain_order=True)
        .sort("codigo_sigtap")
    )
    for r in codes.iter_rows(named=True):
        old_real, cur = r["valor_sigtap_mais_antigo_real"], r["valor_sigtap_real"]
        change = cur / old_real - 1
        c0 = f"{r['competencia_mais_antiga'][4:]}/{r['competencia_mais_antiga'][:4]}"
        c1 = f"{r['competencia_sigtap'][4:]}/{r['competencia_sigtap'][:4]}"
        same_nominal = r["valor_sigtap_mais_antigo_nominal"] == r["valor_sigtap_nominal"]
        nominal_txt = (
            f"o valor nominal ficou em {fmt.brl(r['valor_sigtap_nominal'])} de {c0} a {c1}, sem reajuste"
            if same_nominal
            else f"o valor nominal foi de {fmt.brl(r['valor_sigtap_mais_antigo_nominal'])} ({c0}) para "
            f"{fmt.brl(r['valor_sigtap_nominal'])} ({c1})"
        )
        verbo = "perdeu" if change < 0 else "ganhou"
        frase = (
            f'Tabela SUS, procedimento "{r["descricao_sigtap"]}" (SIGTAP {r["codigo_sigtap_fmt"]}): {nominal_txt}. '
            f"Corrigido pelo IPCA, o valor de {c0} equivale a {fmt.brl(old_real)} em R$ de {mes_ref}: "
            f"em termos reais, o valor de tabela {verbo} {fmt.pct(abs(change), 0)} no período. "
            "Competências comparadas: janeiro de cada ano desde 2015 e a mais recente."
        )
        out.append(
            _finding(
                id=f"sigtap_real_{r['codigo_sigtap']}",
                tipo="defasagem_sigtap",
                familia=r["familia"],
                titulo=f"Tabela SUS, {r['familia'].lower()} (SIGTAP {r['codigo_sigtap_fmt']}): valor real {'caiu' if change < 0 else 'subiu'} {fmt.pct(abs(change), 0)} desde {c0}",
                frase=frase,
                numeros={
                    "codigo_sigtap": r["codigo_sigtap"],
                    "valor_nominal_inicio": r["valor_sigtap_mais_antigo_nominal"],
                    "valor_nominal_fim": r["valor_sigtap_nominal"],
                    "valor_real_inicio": old_real,
                    "valor_real_fim": cur,
                    "variacao": change,
                },
                n=0,
                n_descricao="tabela oficial (sem amostragem)",
                periodo=f"{c0} a {c1}",
                unidade="R$ por unidade de OPME (reais)",
                fonte=f"{FONTE_SIGTAP}; IPCA/BCB",
                robustez="forte",
                motivo_robustez="valor oficial de tabela corrigido pelo IPCA; não depende de amostra nem do mapa CATMAT",
                _magnitude=min(abs(change), 1) * 30,
            )
        )
    return out


def build_findings(
    gold: dict[str, pl.DataFrame], comp: pl.DataFrame, period: Period, settings: Settings
) -> pl.DataFrame:
    mes_ref = fmt.month(comp["mes_ref_deflacao"].max())
    rows: list[dict] = []
    rows += _dispersion_findings(gold["dispersao_item"], mes_ref)
    rows += _national_findings(gold["preco_item_uf"], settings, mes_ref)
    rows += _trend_findings(comp, settings, mes_ref, period)
    rows += _concentration_findings(gold["fornecedores_item"], settings, period)
    if "importacao_ncm_ano" in gold:
        rows += _import_findings(
            gold["importacao_ncm_ano"], gold.get("ponte_preco_importacao"), mes_ref
        )
    if "anvisa_registros_familia" in gold:
        snap = str(comp["snapshot"].max())[:10]
        rows += _anvisa_findings(gold["anvisa_registros_familia"], snap)
    if "ponte_sigtap_preco" in gold and gold["ponte_sigtap_preco"].height:
        rows += _sigtap_findings(gold["ponte_sigtap_preco"], settings, mes_ref)
    if not rows:
        logger.warning("Nenhum achado gerado.")
    df = pl.DataFrame(rows, infer_schema_length=None)
    df = df.with_columns(
        pl.col("codigo_catmat").cast(pl.Int64),
        pl.col("n").cast(pl.Int64),
        pl.lit(mes_ref).alias("mes_ref"),
    )
    # Diversidade: dentro do mesmo nível de robustez, primeiro o melhor achado de cada tipo,
    # depois o segundo melhor de cada tipo, e assim por diante.
    df = df.with_columns(
        pl.col("robustez").replace_strict(WEIGHT, return_dtype=pl.Int64).alias("_w"),
    ).with_columns(
        pl.col("score").rank("ordinal", descending=True).over(["_w", "tipo"]).alias("_rt"),
    )
    df = (
        df.sort(["_w", "_rt", "score", "id"], descending=[True, False, True, False])
        .drop("_w", "_rt")
        .head(settings.findings.max_findings)
    )
    return df.with_columns(pl.int_range(1, pl.len() + 1).alias("rank"))


def write_findings_doc(settings: Settings, achados: pl.DataFrame, meta: dict) -> None:
    """docs/ACHADOS.md: os 10 melhores achados com a evidência de cada um."""
    top = achados.head(settings.findings.top_for_docs)
    lines = [
        "# Achados",
        "",
        f"Gerado por `uv run raiox analyze` a partir dos dados de {meta['snapshot_dados']}. "
        f"Período das compras: {meta['periodo_label']}. Valores em R$ de {fmt.month(date.fromisoformat(meta['mes_ref_deflacao']))} (IPCA).",
        "",
        "Robustez: **forte** = passa em todas as regras da seção 8 (só estes vão para post); "
        "**moderado** = indício que merece investigação, com ressalva; **fraco** = não publicar.",
        "",
        "| # | Robustez | Achado | n | Período |",
        "|---:|---|---|---|---|",
    ]
    for r in top.iter_rows(named=True):
        lines.append(
            f"| {r['rank']} | {r['robustez']} | {r['titulo']} | {r['n_descricao']} | {r['periodo']} |"
        )
    lines += ["", "## Evidência de cada achado", ""]
    for r in top.iter_rows(named=True):
        nums = json.loads(r["numeros"])
        lines += [
            f"### {r['rank']}. {r['titulo']}",
            "",
            f"> {r['frase']}",
            "",
            f"- **Tipo:** {r['tipo']} · **Robustez:** {r['robustez']} ({r['motivo_robustez']})",
            f"- **Base (n):** {r['n_descricao']} · **Período:** {r['periodo']} · **Unidade:** {r['unidade']}",
            f"- **Fonte:** {r['fonte']}",
            "- **Números:** "
            + "; ".join(
                f"`{k}` = {v if not isinstance(v, float) else round(v, 4)}" for k, v in nums.items()
            ),
            "",
        ]
    lines += [
        "## Todos os achados",
        "",
        f"A tabela completa ({achados.height} achados, inclusive moderados e fracos) está em `data/gold/achados.parquet` e na página inicial do painel.",
        "",
    ]
    path = settings.root / "docs" / "ACHADOS.md"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    marker = "## Conferência contra o raw"
    tail = existing[existing.index(marker) :] if marker in existing else ""
    path.write_text("\n".join(lines) + ("\n" + tail if tail else ""), encoding="utf-8")
