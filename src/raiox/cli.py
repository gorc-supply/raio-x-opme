"""CLI `raiox` (typer). Toda automação do projeto roda por aqui: `uv run raiox <comando>`."""

from __future__ import annotations

import os
import sys

import typer

from raiox.config import get_settings
from raiox.logs import logger, setup_logging

# Consoles do Windows (cp1252) quebram com acentos/setas: força UTF-8 na saída.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure") and (_stream.encoding or "").lower() != "utf-8":
        _stream.reconfigure(encoding="utf-8", errors="replace")

app = typer.Typer(
    help="Raio-X OPME: quanto o setor público paga por stents, próteses e implantes.",
    no_args_is_help=True,
    add_completion=False,
)
ingest_app = typer.Typer(help="Ingestão das fontes (raw + bronze).", no_args_is_help=True)
catalog_app = typer.Typer(help="Catálogo curado de itens OPME (Fase 2).", no_args_is_help=True)
fixtures_app = typer.Typer(
    help="Amostras reais pequenas para testes e modo offline.", no_args_is_help=True
)
app.add_typer(ingest_app, name="ingest")
app.add_typer(catalog_app, name="catalog")
app.add_typer(fixtures_app, name="fixtures")

OfflineOpt = typer.Option(False, "--offline", help="Usa só data/fixtures (sem rede).")
ForceOpt = typer.Option(False, "--force", help="Ignora o cache do dia e chama a fonte de novo.")


def _settings(offline: bool):
    if offline:
        os.environ["RAIOX_OFFLINE"] = "1"
    s = get_settings(offline=offline)
    setup_logging(s)
    if offline:
        logger.info("Modo offline: lendo data/fixtures e gravando em {}", s.paths.offline_root)
    return s


# ---------------------------------------------------------------- ingest ----
@ingest_app.command("compras")
def ingest_compras(offline: bool = OfflineOpt, force: bool = ForceOpt) -> None:
    """Preços praticados (Compras.gov.br) para cada item do catálogo."""
    from raiox.pipeline import run_ingest

    run_ingest(_settings(offline), ["compras"], force=force)


@ingest_app.command("comex")
def ingest_comex(offline: bool = OfflineOpt, force: bool = ForceOpt) -> None:
    """Importação e exportação por NCM (ComexStat/MDIC)."""
    from raiox.pipeline import run_ingest

    run_ingest(_settings(offline), ["comex"], force=force)


@ingest_app.command("bcb")
def ingest_bcb(offline: bool = OfflineOpt, force: bool = ForceOpt) -> None:
    """IPCA e câmbio (Banco Central, SGS)."""
    from raiox.pipeline import run_ingest

    run_ingest(_settings(offline), ["bcb"], force=force)


@ingest_app.command("ibge")
def ingest_ibge(offline: bool = OfflineOpt, force: bool = ForceOpt) -> None:
    """UFs e malha GeoJSON (IBGE)."""
    from raiox.pipeline import run_ingest

    run_ingest(_settings(offline), ["ibge"], force=force)


@ingest_app.command("complementares")
def ingest_complementary(offline: bool = OfflineOpt, force: bool = ForceOpt) -> None:
    """Fontes complementares habilitadas em settings.yaml (ANVISA, BPS, itens PNCP)."""
    from raiox.pipeline import run_ingest

    run_ingest(_settings(offline), ["complementares"], force=force)


@ingest_app.command("all")
def ingest_all(offline: bool = OfflineOpt, force: bool = ForceOpt) -> None:
    """Todas as fontes do núcleo."""
    from raiox.pipeline import CORE_SOURCES, run_ingest

    run_ingest(_settings(offline), CORE_SOURCES, force=force)


# --------------------------------------------------------------- catalog ----
@catalog_app.command("build")
def catalog_build(force: bool = ForceOpt) -> None:
    """Descobre itens CATMAT (por NCM e por termos) e gera config/itens_opme.yaml."""
    from raiox.sources.catmat import build_catalog

    build_catalog(_settings(False), force=force)


# -------------------------------------------------------------- fixtures ----
@fixtures_app.command("build")
def fixtures_build() -> None:
    """Copia amostras pequenas do raw mais recente para data/fixtures/raw."""
    from raiox.fixtures import build_fixtures

    build_fixtures(_settings(False))


# ----------------------------------------------------------------- stages ----
@app.command()
def recon() -> None:
    """Fase 1: chamadas mínimas a cada fonte, contrato e latência (gera data/reference/recon.json)."""
    from raiox.recon import run_recon

    run_recon(_settings(False))


@app.command()
def transform(offline: bool = OfflineOpt) -> None:
    """Bronze → silver (limpeza, unidades, deduplicação, CPF mascarado, outliers, deflação)."""
    from raiox.pipeline import run_transform

    run_transform(_settings(offline))


@app.command()
def quality(offline: bool = OfflineOpt) -> None:
    """Relatório de qualidade (data/gold/qualidade.parquet e docs/QUALIDADE.md)."""
    from raiox.pipeline import run_quality

    run_quality(_settings(offline))


@app.command()
def analyze(offline: bool = OfflineOpt) -> None:
    """Silver → gold (preços por UF, dispersão, séries, concentração, importação, achados)."""
    from raiox.pipeline import run_analyze

    run_analyze(_settings(offline))


@app.command()
def charts(offline: bool = OfflineOpt) -> None:
    """Gráficos PNG 1080×1350 e carrossel PDF para o LinkedIn."""
    from raiox.pipeline import run_charts

    run_charts(_settings(offline))


@app.command("all")
def run_all(offline: bool = OfflineOpt, force: bool = ForceOpt) -> None:
    """Pipeline completo: ingest → transform → quality → analyze → charts."""
    from raiox.pipeline import run_all as _run_all

    status = _run_all(_settings(offline), force=force)
    if not status["ok"] and not offline:
        logger.error("Fontes com falha: {}. Saindo com código 3.", status["failed_sources"])
        raise typer.Exit(code=3)


@app.command()
def version() -> None:
    """Mostra a versão."""
    from raiox import __version__

    typer.echo(__version__)


if __name__ == "__main__":
    app()
