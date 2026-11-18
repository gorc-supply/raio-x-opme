"""Orquestração: ingest → transform → quality → analyze → charts.

Cada etapa também roda isolada pela CLI. Rodar duas vezes seguidas produz a
mesma gold (idempotência): nada de data/hora de execução dentro das tabelas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from raiox.bronze import read_bronze
from raiox.config import Settings, load_catalog
from raiox.http import HttpClient
from raiox.logs import logger
from raiox.state import mark_run, resolve_snapshot

CORE_SOURCES = ["ibge", "bcb", "compras", "comex"]


class PipelineError(RuntimeError):
    pass


# ================================================================ INGEST ====
def _ingest_one(settings: Settings, source: str, force: bool) -> dict[str, Any]:
    snap = resolve_snapshot(settings, source, force)
    if snap:
        mark_run(settings, source, snap, complete=False)
    with HttpClient(settings, source, snapshot=snap, force=force) as client:
        if source == "compras":
            from raiox.sources import compras

            items = load_catalog(settings)
            if not items:
                raise PipelineError(
                    "config/itens_opme.yaml vazio: rode `raiox catalog build` antes."
                )
            counts = compras.ingest(settings, client, items)
        elif source == "comex":
            from raiox.sources import comexstat

            counts = comexstat.ingest(settings, client)
        elif source == "bcb":
            from raiox.sources import bcb

            counts = bcb.ingest(settings, client)
        elif source == "ibge":
            from raiox.sources import ibge

            counts = ibge.ingest(settings, client)
        else:
            raise ValueError(f"Fonte desconhecida: {source}")
        stats = dict(client.stats)
        complete = stats["failed"] == 0
        if snap:
            mark_run(
                settings, source, client.snapshot, complete=complete, counts=counts, stats=stats
            )
    logger.info(
        "Ingestão {} [{}]: {} | rede={} cache={} falhas={}{}",
        source,
        client.snapshot,
        counts,
        stats["network"],
        stats["cache"],
        stats["failed"],
        "" if complete else " (incompleta: a próxima execução retoma este snapshot)",
    )
    return {"counts": counts, "stats": stats, "complete": complete}


def run_ingest(settings: Settings, sources: list[str], force: bool = False) -> dict[str, Any]:
    results: dict[str, Any] = {}
    if "complementares" in sources:
        from raiox.sources import complementary

        results["complementares"] = complementary.ingest(settings, force=force)
        sources = [s for s in sources if s != "complementares"]
    for src in sources:
        try:
            results[src] = _ingest_one(settings, src, force)
        except PipelineError:
            raise
        except Exception as exc:  # noqa: BLE001 — uma fonte não derruba as outras
            logger.exception(
                "Ingestão de {} falhou: {!r}. Seguindo para a próxima fonte.", src, exc
            )
            results[src] = {"error": repr(exc)}
    return results


# ============================================================= TRANSFORM ====
def _write(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path, statistics=False)


def stable_floats(df: pl.DataFrame, sig: int = 10) -> pl.DataFrame:
    """Arredonda floats a `sig` algarismos significativos: somas paralelas do polars podem
    variar na 16ª casa entre execuções; isso garante gold idêntica (idempotência)."""
    cols = [c for c, t in df.schema.items() if t in (pl.Float64, pl.Float32)]
    return df.with_columns(pl.col(c).round_sig_figs(sig) for c in cols) if cols else df


def run_transform(settings: Settings) -> dict[str, Any]:
    from raiox import schemas
    from raiox.transform import normalize as nz

    silver = settings.path("silver")
    counts: dict[str, Any] = {}

    ufs_b = read_bronze(settings, "ufs")
    if ufs_b.height == 0:
        ref = settings.path("reference") / "ufs.csv"
        if not ref.exists():
            ref = settings.root / settings.paths.reference / "ufs.csv"
        ufs_b = pl.read_csv(ref)
    ufs = schemas.validate(nz.silver_ufs(ufs_b), schemas.UFS_SILVER)
    _write(ufs, silver / "ufs.parquet")

    ipca_b = read_bronze(settings, "ipca")
    if ipca_b.height == 0:
        raise PipelineError("Sem IPCA na bronze: rode `raiox ingest bcb`.")
    index = schemas.validate(nz.silver_ipca(ipca_b), schemas.IPCA_SILVER)
    _write(index, silver / "ipca.parquet")
    counts["ipca_meses"] = index.height

    fx_b = read_bronze(settings, "cambio")
    if fx_b.height:
        fx = schemas.validate(nz.silver_cambio(fx_b), schemas.CAMBIO_SILVER)
        _write(fx, silver / "cambio.parquet")
        counts["cambio_meses"] = fx.height

    for table in ("comex_import", "comex_export"):
        b = read_bronze(settings, table)
        if b.height:
            df = schemas.validate(nz.silver_comex(b, settings, ufs), schemas.COMEX_SILVER)
            _write(df, silver / f"{table}.parquet")
            counts[table] = df.height

    cat_b = read_bronze(settings, "catmat_itens")
    if cat_b.height:
        cat = (
            cat_b.sort("_snapshot")
            .unique(subset=["codigoItem"], keep="last")
            .drop("_source", "_fetched_at")
        )
        _write(cat, silver / "catmat_itens.parquet")
        counts["catmat_itens"] = cat.height

    anv_b = read_bronze(settings, "anvisa_produtos")
    if anv_b.height:
        from datetime import date as _date

        from raiox.sources import anvisa

        ref = _date.fromisoformat(max(anv_b["_snapshot"].unique().to_list())[:10])
        anv = anvisa.silver(anv_b, ref)
        _write(anv, silver / "anvisa_produtos.parquet")
        counts["anvisa_produtos"] = anv.height

    comp_b = read_bronze(settings, "compras_precos")
    if comp_b.height == 0:
        raise PipelineError("Sem preços na bronze: rode `raiox ingest compras`.")
    catalog = load_catalog(settings)
    comp, discards, ccounts = nz.silver_compras(comp_b, catalog, ufs, index, settings.analysis)
    comp = schemas.validate(comp, schemas.COMPRAS_SILVER)
    _write(comp, silver / "compras_precos.parquet")
    _write(discards, silver / "compras_descartes.parquet")
    counts["compras"] = ccounts
    counts["snapshots_compras"] = sorted(comp_b["_snapshot"].unique().to_list())
    (silver / "_contagens.json").write_text(
        json.dumps(counts, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )
    logger.info(
        "Silver: {} preços válidos, {} descartes, {} outliers marcados",
        ccounts["silver"],
        discards.height,
        ccounts["outliers"],
    )
    return counts


# =============================================================== QUALITY ====
def run_quality(settings: Settings) -> pl.DataFrame:
    from raiox.transform.quality import build_quality

    return build_quality(settings)


# =============================================================== ANALYZE ====
def run_analyze(settings: Settings) -> dict[str, int]:
    from raiox import schemas
    from raiox.analytics import concentration, dispersion, findings, imports

    silver_dir = settings.path("silver")
    gold = settings.path("gold")
    gold.mkdir(parents=True, exist_ok=True)
    cfg = settings.analysis

    comp = pl.read_parquet(silver_dir / "compras_precos.parquet")
    index = pl.read_parquet(silver_dir / "ipca.parquet")
    period = dispersion.analysis_period(comp, cfg)
    logger.info("Período de análise: {} (R$ de {:%m/%Y})", period.label, index["mes"].max())

    out: dict[str, pl.DataFrame] = {}
    out["preco_item_uf"] = schemas.validate(
        dispersion.preco_item_uf(comp, period, cfg), schemas.PRECO_ITEM_UF
    )
    out["dispersao_item"] = schemas.validate(
        dispersion.dispersao_item(comp, out["preco_item_uf"], period, cfg), schemas.DISPERSAO_ITEM
    )
    out["serie_item_mes"] = schemas.validate(
        dispersion.serie_item_mes(comp, cfg), schemas.SERIE_ITEM_MES
    )
    out["fornecedores_item"] = schemas.validate(
        concentration.fornecedores_item(comp, period, cfg.top_n_concentration),
        schemas.FORNECEDORES_ITEM,
    )

    from raiox.state import read_state

    price_path = (read_state(settings, "compras_price_path") or {}).get(
        "path", settings.compras.price_path_candidates[0]
    )
    out["compras_detalhe"] = dispersion.compras_detalhe(
        comp, period, settings.compras.base_url, price_path
    )

    imp_path = silver_dir / "comex_import.parquet"
    if imp_path.exists():
        imp = pl.read_parquet(imp_path)
        exp_path = silver_dir / "comex_export.parquet"
        exp = pl.read_parquet(exp_path) if exp_path.exists() else pl.DataFrame()
        fx = pl.read_parquet(silver_dir / "cambio.parquet")
        units = imports.load_ncm_units(settings.root / settings.paths.reference)
        specific = {n.ncm: n.especifico for n in settings.comex.ncms}
        imp_ano, origem = imports.importacao_ncm_ano(
            imp, exp, fx, index, units, cfg.top_n_concentration, specific
        )
        out["importacao_ncm_ano"] = schemas.validate(imp_ano, schemas.IMPORTACAO_NCM_ANO)
        out["importacao_origem"] = origem
        out["ponte_preco_importacao"] = schemas.validate(
            imports.ponte_preco_importacao(imp_ano, comp, period, cfg.bridge_years),
            schemas.PONTE,
        )
    else:
        logger.warning("Sem dados de comércio exterior na silver: tabelas de importação puladas.")

    anv_path = silver_dir / "anvisa_produtos.parquet"
    if anv_path.exists():
        from raiox.sources import anvisa

        out["anvisa_registros_familia"] = anvisa.gold_by_family(pl.read_parquet(anv_path))

    out["achados"] = schemas.validate(
        findings.build_findings(out, comp, period, settings), schemas.ACHADOS
    )
    schemas.check_language(out["achados"]["frase"].to_list())

    for name, df in out.items():
        _write(stable_floats(df), gold / f"{name}.parquet")
        logger.info("Gold {}: {} linhas", name, df.height)

    meta = {
        "periodo_inicio": period.start.isoformat(),
        "periodo_fim": period.end.isoformat(),
        "periodo_label": period.label,
        "mes_ref_deflacao": index["mes"].max().isoformat(),
        "snapshot_dados": dispersion.snapshot_date(comp).isoformat(),
        "n_itens": int(comp["codigo_catmat"].n_unique()),
        "n_compras_periodo": int(period.filter(comp)["id_compra"].n_unique()),
        "n_registros_periodo": int(period.filter(comp).height),
        "n_ufs_periodo": int(period.filter(comp)["uf"].n_unique()),
        "n_compras_total": int(comp["id_compra"].n_unique()),
        "data_compra_min": comp["data_compra"].min().isoformat(),
        "data_compra_max": comp["data_compra"].max().isoformat(),
        "regras": {
            "min_compras_uf": cfg.min_purchases_per_uf,
            "min_orgaos_uf": cfg.min_buyers_per_uf,
            "bootstrap_reps": cfg.bootstrap_reps,
            "ic": cfg.ci_level,
            "ic_inferior_minimo": cfg.finding_min_ci_lower,
            "max_share_orgao": cfg.max_top_buyer_share,
        },
    }
    (gold / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    if not settings.offline:
        findings.write_findings_doc(settings, out["achados"], meta)
    return {k: v.height for k, v in out.items()}


# ================================================================ CHARTS ====
def run_charts(settings: Settings) -> list[Path]:
    from raiox.viz.linkedin import build_all

    return build_all(settings)


# =================================================================== ALL ====
def run_all(settings: Settings, force: bool = False) -> dict[str, Any]:
    """Pipeline completo. Retorna o status das fontes; `ok=False` se alguma fonte do núcleo
    falhou ou ficou incompleta (a CLI sai com código 3 e o workflow preserva a gold anterior)."""
    from raiox.sources.complementary import enabled

    extra = ["complementares"] if enabled(settings) else []
    results = run_ingest(settings, CORE_SOURCES + extra, force=force)
    failed = [
        s
        for s in CORE_SOURCES
        if "error" in results.get(s, {}) or not results.get(s, {}).get("complete", False)
    ]
    run_transform(settings)
    run_quality(settings)
    run_analyze(settings)
    run_charts(settings)
    if failed:
        logger.warning("Pipeline concluído, mas com fontes falhas/incompletas: {}", failed)
    else:
        logger.info("Pipeline completo.")
    return {"ok": not failed, "failed_sources": failed, "ingest": results}
