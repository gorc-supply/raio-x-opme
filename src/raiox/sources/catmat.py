"""Fase 2 — catálogo curado de itens OPME (`raiox catalog build`).

Descoberta em duas frentes, cruzadas no fim:
  (a) por NCM: itens CATMAT cujo `codigo_ncm` está na lista de NCMs do projeto;
  (b) por termos: PDMs do grupo 65 cujo nome contém os termos de busca
      (a API não busca por substring em `descricaoItem`, então o filtro é local).
Para cada PDM candidato, a API de preços é consultada por PDM na janela de
contagem, o que dá o nº de compras distintas por item de uma vez só.
Seleção: itens ativos, com compras suficientes e unidade dominante clara,
distribuídos entre famílias (round-robin por volume).

Re-executar preserva `nome_curto` e `nota_comparabilidade` editados à mão.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from typing import Any

import yaml

from raiox.config import Settings, load_catalog
from raiox.http import HttpClient
from raiox.logs import logger
from raiox.sources.compras import ComprasSource

SOURCE = "catmat"


def norm(text: str | None) -> str:
    """Maiúsculas, sem acento, espaços colapsados (chave de comparação)."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.upper()).strip()


# Regras de família: (termo no nome do PDM normalizado, termo opcional na descrição, família)
FAMILY_RULES: list[tuple[str, str | None, str]] = [
    ("ENDOPROTESE CORONARIA", "NAO FARMACOLOGICO", "Stent coronário convencional"),
    ("ENDOPROTESE CORONARIA", "FARMACOLOGICO", "Stent coronário farmacológico"),
    ("ENDOPROTESE CORONARIA", None, "Stent coronário (outros)"),
    ("ENDOPROTESE VASCULAR PERIFERICA", None, "Stent vascular periférico"),
    ("ENDOPROTESE DE AORTA", None, "Endoprótese de aorta"),
    ("PROTESE DE QUADRIL", None, "Prótese de quadril"),
    ("PROTESE DE JOELHO", None, "Prótese de joelho"),
    ("PARAFUSO", None, "Parafusos ortopédicos"),
    ("PLACA", None, "Placas ortopédicas"),
    ("HASTE INTRAMEDULAR", None, "Hastes intramedulares"),
    ("MARCA-PASSO", None, "Marca-passo"),
    ("MARCAPASSO", None, "Marca-passo"),
    ("VALVULAR CARDIACA", "BIOLOGICA", "Válvula cardíaca biológica"),
    ("VALVULAR CARDIACA", "MECANICA", "Válvula cardíaca mecânica"),
    ("CATETER BALAO", None, "Cateter balão"),
]

# NCM de referência por família (usado se o item não trouxer codigo_ncm no CATMAT).
FAMILY_NCM_FALLBACK = {
    "Stent coronário convencional": "90219012",
    "Stent coronário farmacológico": "90219012",
    "Stent coronário (outros)": "90219012",
    "Stent vascular periférico": "90219012",
    "Prótese de quadril": "90213110",
    "Prótese de joelho": "90213190",
    "Parafusos ortopédicos": "90211020",
    "Placas ortopédicas": "90211020",
    "Hastes intramedulares": "90211020",
    "Marca-passo": "90215000",
    "Válvula cardíaca biológica": "90213919",
    "Válvula cardíaca mecânica": "90213911",
}

# Família "macro" usada nos gráficos e na ponte com a importação.
MACRO_FAMILY = {
    "Stent coronário convencional": "Stents",
    "Stent coronário farmacológico": "Stents",
    "Stent coronário (outros)": "Stents",
    "Stent vascular periférico": "Stents",
    "Endoprótese de aorta": "Próteses vasculares",
    "Prótese de quadril": "Próteses articulares",
    "Prótese de joelho": "Próteses articulares",
    "Parafusos ortopédicos": "Placas, parafusos e hastes",
    "Placas ortopédicas": "Placas, parafusos e hastes",
    "Hastes intramedulares": "Placas, parafusos e hastes",
    "Marca-passo": "Marca-passos",
    "Válvula cardíaca biológica": "Válvulas cardíacas",
    "Válvula cardíaca mecânica": "Válvulas cardíacas",
    "Cateter balão": "Cateteres",
}


def classify(nome_pdm: str, descricao: str) -> str | None:
    p, d = norm(nome_pdm), norm(descricao)
    for pdm_term, desc_term, fam in FAMILY_RULES:
        if pdm_term in p and (desc_term is None or desc_term in d):
            return fam
    return None


def short_name(descricao: str, familia: str) -> str:
    """Nome curto automático: família + atributos mais distintivos (editável no YAML)."""
    d = norm(descricao)
    parts: list[str] = []
    dim = re.search(r"DIMENSAO: ([^,]+?)(?: ,|,|$)", d)
    if dim:
        parts.append(dim.group(1).replace("CERCA DE ", "").replace(" X ", " × ").lower())
    for attr in ("TIPO", "MODELO", "MATERIAL", "DIAMETRO", "COMPRIMENTO", "CAMARA"):
        m = re.search(rf"{attr}: ([^,]+?)(?: ,|,|$)", d)
        if m and len(parts) < 3:
            val = m.group(1).strip().lower()
            if val and val not in " ".join(parts):
                parts.append(val)
    base = familia
    return f"{base} — {', '.join(parts[:3])}" if parts else base


def _months_ago(months: int) -> str:
    today = date.today()
    y, m = today.year, today.month - months
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1).isoformat()


def build_catalog(settings: Settings, force: bool = False) -> list[dict[str, Any]]:
    cfg = settings.catalog
    with HttpClient(settings, SOURCE, force=force) as client:
        src = ComprasSource(settings, client)

        # (b) PDMs por termo -------------------------------------------------
        terms = [norm(t) for t in cfg.search_terms]
        pdms = list(src.iter_pdms(settings.compras.catalog_group))
        term_pdms = {
            int(p["codigoPdm"]): p["nomePdm"]
            for p in pdms
            if p.get("statusPdm") and any(t in norm(p["nomePdm"]) for t in terms)
        }
        logger.info(
            "Catálogo: {} PDMs no grupo 65; {} casam com os termos", len(pdms), len(term_pdms)
        )

        items: dict[int, dict[str, Any]] = {}
        via: dict[int, set[str]] = defaultdict(set)
        for pdm in sorted(term_pdms):
            for it in src.iter_catalog(f"catalogo_pdm_{pdm}", codigoPdm=pdm):
                items[int(it["codigoItem"])] = it
                via[int(it["codigoItem"])].add("termo")

        # (a) itens por NCM ----------------------------------------------------
        for n in settings.comex.ncms:
            if n.historico:
                continue
            for it in src.iter_catalog(f"catalogo_ncm_{n.ncm}", codigo_ncm=n.ncm):
                items[int(it["codigoItem"])] = it
                via[int(it["codigoItem"])].add("ncm")
        active = {k: v for k, v in items.items() if v.get("statusItem")}
        logger.info("Catálogo: {} itens candidatos ({} ativos)", len(items), len(active))

        # Só PDMs cujos itens caem numa família conhecida entram na contagem.
        pdm_family: dict[int, set[str]] = defaultdict(set)
        for it in active.values():
            fam = classify(it.get("nomePdm", ""), it.get("descricaoItem", ""))
            if fam:
                pdm_family[int(it["codigoPdm"])].add(fam)
        logger.info("Catálogo: {} PDMs com família reconhecida", len(pdm_family))

        # Contagem de compras por item via consulta por PDM na janela ---------
        start = _months_ago(cfg.count_window_months)
        end = date.today().isoformat()
        stats: dict[int, dict[str, Any]] = defaultdict(
            lambda: {"compras": set(), "orgaos": set(), "ufs": set(), "unidades": Counter(), "n": 0}
        )
        for pdm in sorted(pdm_family):
            n_rows = 0
            for row in src.iter_prices(
                pdm,
                tipo="codigoPdm",
                # A API ignora dataCompraInicio sem dataCompraFim (verificado na Fase 2).
                extra={"dataCompraInicio": start, "dataCompraFim": end},
                key_prefix=f"contagem_pdm_{pdm}_{start}_{end}",
            ):
                if (row.get("dataCompra") or "") < start:
                    continue
                code = int(row["codigoItemCatalogo"])
                st = stats[code]
                st["n"] += 1
                st["compras"].add(row.get("idCompra"))
                st["orgaos"].add(row.get("codigoUasg"))
                if row.get("estado"):
                    st["ufs"].add(row["estado"])
                st["unidades"][(row.get("siglaUnidadeFornecimento") or "?").upper()] += 1
                n_rows += 1
            logger.info("Contagem PDM {} ({}): {} registros", pdm, sorted(pdm_family[pdm]), n_rows)

    # Monta candidatos ---------------------------------------------------------
    previous = {int(i["codigo_catmat"]): i for i in load_catalog(settings)}
    cands = []
    for code, it in active.items():
        fam = classify(it.get("nomePdm", ""), it.get("descricaoItem", ""))
        st = stats.get(code)
        if not fam or not st or st["n"] == 0:
            continue
        unit, unit_n = st["unidades"].most_common(1)[0]
        cands.append(
            {
                "codigo_catmat": code,
                "descricao_oficial": it.get("descricaoItem", "").strip(),
                "familia": fam,
                "familia_macro": MACRO_FAMILY.get(fam, fam),
                "codigo_pdm": int(it["codigoPdm"]),
                "nome_pdm": it.get("nomePdm"),
                "ncm": it.get("codigo_ncm") or FAMILY_NCM_FALLBACK.get(fam),
                "ncm_origem": "catmat" if it.get("codigo_ncm") else "regra_familia",
                "unidade_dominante": unit,
                "share_unidade_dominante": round(unit_n / st["n"], 3),
                "n_registros": st["n"],
                "n_compras": len(st["compras"]),
                "n_orgaos": len(st["orgaos"]),
                "n_ufs": len(st["ufs"]),
                "origem": "+".join(sorted(via[code])),
            }
        )
    eligible = [
        c
        for c in cands
        if c["n_compras"] >= cfg.min_purchases and c["share_unidade_dominante"] >= 0.8
    ]
    logger.info("Catálogo: {} itens com compras; {} elegíveis", len(cands), len(eligible))

    by_fam: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in sorted(eligible, key=lambda c: (-c["n_compras"], -c["n_ufs"])):
        by_fam[c["familia"]].append(c)
    fam_order = sorted(by_fam, key=lambda f: -by_fam[f][0]["n_compras"])
    selected: list[dict[str, Any]] = []
    for rnd in range(cfg.max_items_per_family):
        for fam in fam_order:
            if len(selected) >= cfg.max_items:
                break
            if rnd < len(by_fam[fam]):
                selected.append(by_fam[fam][rnd])

    for c in selected:
        prev = previous.get(c["codigo_catmat"], {})
        c["nome_curto"] = prev.get("nome_curto") or short_name(c["descricao_oficial"], c["familia"])
        c["nota_comparabilidade"] = prev.get("nota_comparabilidade") or (
            f"Comparação restrita ao CATMAT {c['codigo_catmat']} em '{c['unidade_dominante']}'"
            f" ({c['share_unidade_dominante']:.0%} dos registros nessa unidade na contagem)."
        )

    families = {c["familia"] for c in selected}
    if len(selected) < cfg.min_items or len(families) < cfg.min_families:
        logger.error(
            "Catálogo abaixo do mínimo: {} itens, {} famílias (mín. {} e {})",
            len(selected),
            len(families),
            cfg.min_items,
            cfg.min_families,
        )

    order = [
        "codigo_catmat",
        "nome_curto",
        "familia",
        "familia_macro",
        "descricao_oficial",
        "ncm",
        "ncm_origem",
        "unidade_dominante",
        "share_unidade_dominante",
        "n_compras",
        "n_registros",
        "n_orgaos",
        "n_ufs",
        "codigo_pdm",
        "nome_pdm",
        "origem",
        "nota_comparabilidade",
    ]
    selected.sort(key=lambda c: (c["familia_macro"], c["familia"], -c["n_compras"]))
    doc = {
        "gerado_em": date.today().isoformat(),
        "janela_contagem": f"{start} em diante ({cfg.count_window_months} meses)",
        "criterios": {
            "min_compras": cfg.min_purchases,
            "share_minimo_unidade_dominante": 0.8,
            "max_itens_por_familia": cfg.max_items_per_family,
            "max_itens": cfg.max_items,
        },
        "itens": [{k: c[k] for k in order} for c in selected],
    }
    out = settings.root / "config" / "itens_opme.yaml"
    header = (
        "# Catálogo curado de itens OPME — gerado por `uv run raiox catalog build`.\n"
        "# nome_curto e nota_comparabilidade podem ser editados à mão: são preservados ao regerar.\n"
        "# n_compras = compras distintas (idCompra) na janela de contagem.\n"
    )
    out.write_text(
        header + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    # Relatório de todos os candidatos (auditoria da seleção).
    import polars as pl

    ref = settings.path("reference")
    if cands:
        pl.DataFrame(cands).sort("n_compras", descending=True).write_csv(
            ref / "catalogo_candidatos.csv"
        )
    logger.info("Catálogo: {} itens em {} famílias → {}", len(selected), len(families), out.name)
    return selected
