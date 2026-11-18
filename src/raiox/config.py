"""Configuração do projeto: lê config/settings.yaml e config/itens_opme.yaml.

Todos os caminhos são resolvidos a partir da raiz do repositório com pathlib,
o que mantém o projeto compatível com Windows. A raiz pode ser sobrescrita pela
variável de ambiente RAIOX_ROOT (útil em testes).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_root() -> Path:
    env = os.environ.get("RAIOX_ROOT")
    if env:
        return Path(env).resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "config").is_dir():
            return parent
    return Path.cwd().resolve()


class ProjectCfg(BaseModel):
    name: str
    author: str
    author_full_name: str
    repo_url: str
    dashboard_url: str
    linkedin_url: str


class PathsCfg(BaseModel):
    raw: str
    bronze: str
    silver: str
    gold: str
    reference: str
    fixtures: str
    state: str
    offline_root: str
    logs: str
    certs: str
    linkedin: str
    docs: str


class HttpCfg(BaseModel):
    timeout_s: float
    max_attempts: int
    backoff_initial_s: float
    backoff_max_s: float
    max_pages: int
    user_agent: str
    rate_limits: dict[str, float]
    icp_brasil_bundle_url: str


class ComprasCfg(BaseModel):
    base_url: str
    price_path_candidates: list[str]
    detail_path: str
    catalog_item_path: str
    catalog_pdm_path: str
    pncp_items_path: str
    openapi_path: str
    page_size: int
    catalog_group: int


class CatalogCfg(BaseModel):
    min_items: int
    max_items: int
    min_families: int
    count_window_months: int
    min_purchases: int
    max_items_per_family: int
    search_terms: list[str]


class NcmCfg(BaseModel):
    ncm: str
    familia: str
    descricao: str
    historico: bool = False
    especifico: bool = True


class ComexCfg(BaseModel):
    base_url: str
    start_year: int
    flows: list[str]
    details: list[str]
    metrics_import: list[str]
    metrics_export: list[str]
    ncms_per_request: int
    pause_s: float
    ncms: list[NcmCfg]


class BcbCfg(BaseModel):
    base_url: str
    ipca_series: int
    fx_series: int
    fx_fallback_daily_series: int
    start_date: str
    window_years: int


class IbgeCfg(BaseModel):
    states_url: str
    geojson_url: str
    geojson_max_bytes: int


class AnalysisCfg(BaseModel):
    period_months: int
    period_start: str | None = None
    period_end: str | None = None
    min_purchases_per_uf: int
    min_buyers_per_uf: int
    outlier_iqr_k: float
    outlier_mad_z: float
    outlier_min_n: int
    bootstrap_reps: int
    bootstrap_seed: int
    ci_level: float
    finding_min_ci_lower: float
    max_top_buyer_share: float
    max_p90_p10_homogeneo: float
    top_n_concentration: int
    min_obs_month: int
    bridge_years: int
    unit_aliases_piece: list[str]
    unit_aliases_pack: list[str]
    unit_aliases_set: list[str]


class FindingsCfg(BaseModel):
    max_findings: int
    top_for_docs: int
    min_compras_forte: int
    min_compras_moderado: int
    janela_tendencia_meses: int
    tendencia_margem: float
    p90_p10_minimo: float
    cr3_minimo: float


class ChartsCfg(BaseModel):
    width_px: int
    height_px: int
    dpi: int
    footer: str


class ComplementaryCfg(BaseModel):
    bps: dict[str, Any] = Field(default_factory=dict)
    pncp_itens: dict[str, Any] = Field(default_factory=dict)
    anvisa: dict[str, Any] = Field(default_factory=dict)
    sigtap: dict[str, Any] = Field(default_factory=dict)


class Settings(BaseSettings):
    """Configuração completa. Variáveis RAIOX_* sobrescrevem chaves de topo se necessário."""

    model_config = SettingsConfigDict(env_prefix="RAIOX_", extra="ignore")

    project: ProjectCfg
    paths: PathsCfg
    http: HttpCfg
    compras: ComprasCfg
    catalog: CatalogCfg
    comex: ComexCfg
    bcb: BcbCfg
    ibge: IbgeCfg
    analysis: AnalysisCfg
    findings: FindingsCfg
    charts: ChartsCfg
    complementary: ComplementaryCfg

    root: Path = Field(default_factory=find_root)
    offline: bool = False

    # ---- caminhos resolvidos -------------------------------------------------
    def path(self, name: str) -> Path:
        """Caminho absoluto de uma pasta de dados.

        Em modo offline, bronze/silver/gold/state/linkedin vão para data/offline/<nome>,
        para que rodar o pipeline com fixtures nunca sobrescreva a gold real.
        """
        rel = getattr(self.paths, name)
        if self.offline and name in {"bronze", "silver", "gold", "state", "linkedin"}:
            return self.root / self.paths.offline_root / name
        if self.offline and name == "raw":
            return self.root / self.paths.fixtures / "raw"
        return self.root / rel

    @property
    def user_agent(self) -> str:
        return self.http.user_agent.format(repo_url=self.project.repo_url)


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=4)
def _load(root: str, offline: bool) -> Settings:
    data = _read_yaml(Path(root) / "config" / "settings.yaml")
    return Settings(**data, root=Path(root), offline=offline)


def get_settings(offline: bool | None = None) -> Settings:
    """Carrega a configuração (com cache). `offline=None` usa RAIOX_OFFLINE do ambiente."""
    if offline is None:
        offline = os.environ.get("RAIOX_OFFLINE", "0") == "1"
    return _load(str(find_root()), offline)


def load_catalog(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Lê config/itens_opme.yaml (lista de itens). Retorna [] se ainda não existir."""
    s = settings or get_settings()
    path = s.root / "config" / "itens_opme.yaml"
    if not path.exists():
        return []
    data = _read_yaml(path)
    return list(data.get("itens", []))
