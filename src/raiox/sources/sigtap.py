"""SIGTAP / DATASUS — Tabela de Procedimentos, Medicamentos e OPM do SUS (Tabela Unificada).

Fonte: a página oficial de download (http://sigtap.datasus.gov.br/tabela-unificada/app/download.jsp
e o RSS `competencias.rss`) aponta para um ZIP por competência no FTP público do DATASUS
(ftp://ftp2.datasus.gov.br/pub/sistemas/tup/downloads/), sem login. Não existe espelho HTTP,
por isso o download usa `ftplib` (biblioteca padrão) com retry e cache no raw.

Cada ZIP traz arquivos TXT de largura fixa (latin-1) e, ao lado, um `<tabela>_layout.txt`
com `Coluna,Tamanho,Inicio,Fim,Tipo`. O layout MUDA entre competências (em 2015 `VL_SH` tinha
10 posições; em 2026, 12), então cada arquivo é fatiado pelo seu próprio layout.

Valor de OPME: campo `VL_SH` ("Serviço Hospitalar" na consulta web), em CENTAVOS
(ex.: 0000000006321 = R$ 63,21). Grupo 07 = Órteses, próteses e materiais especiais.
O SIGTAP é valor de REEMBOLSO do SUS ao prestador, não preço de compra.
"""

from __future__ import annotations

import ftplib
import hashlib
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from raiox.bronze import write_bronze
from raiox.config import Settings
from raiox.http import HttpClient
from raiox.logs import logger

SOURCE = "sigtap"
TABLE = "sigtap_procedimentos"
PROC_FILE = "tb_procedimento.txt"
PROC_LAYOUT = "tb_procedimento_layout.txt"
ZIP_RE = re.compile(r"^TabelaUnificada_(\d{6})_v(\d+)\.zip$", re.IGNORECASE)
LISTING_KEY = "listagem_ftp"
ENCODING = "latin1"


# ------------------------------------------------------------- layout/parser ----
@dataclass(frozen=True)
class Field:
    name: str
    start: int  # 1-based, inclusivo (como no arquivo de layout)
    end: int  # inclusivo
    kind: str


def parse_layout(text: str) -> list[Field]:
    """Lê `Coluna,Tamanho,Inicio,Fim,Tipo` e confere que Tamanho = Fim − Inicio + 1."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines or not lines[0].lower().startswith("coluna"):
        raise ValueError("Layout SIGTAP sem cabeçalho 'Coluna,Tamanho,Inicio,Fim,Tipo'.")
    fields = []
    for ln in lines[1:]:
        name, size, start, end, kind = (p.strip() for p in ln.split(","))
        f = Field(name, int(start), int(end), kind)
        if int(size) != f.end - f.start + 1:
            raise ValueError(f"Layout inconsistente em {name}: tamanho {size} ≠ {start}..{end}")
        fields.append(f)
    return fields


def parse_fixed_width(text: str, layout: list[Field]) -> pl.DataFrame:
    """Fatia cada linha pelo layout. `text` já decodificado em latin-1 (1 caractere = 1 byte,
    então as posições do layout valem para caracteres). Tudo sai como texto, sem espaços."""
    width = max(f.end for f in layout)
    cols: dict[str, list[str]] = {f.name: [] for f in layout}
    for line in text.splitlines():
        if not line.strip():
            continue
        line = line.ljust(width)
        for f in layout:
            cols[f.name].append(line[f.start - 1 : f.end].strip())
    return pl.DataFrame(cols, schema={f.name: pl.String for f in layout})


def _member(zf: zipfile.ZipFile, name: str) -> str:
    for n in zf.namelist():
        if n.lower().endswith(name.lower()):
            return n
    raise KeyError(f"{name} não encontrado no ZIP")


def read_procedures(zip_path: Path, group_prefix: str = "07") -> pl.DataFrame:
    """Procedimentos do grupo `group_prefix` de uma competência, com valores em reais."""
    with zipfile.ZipFile(zip_path) as zf:
        layout = parse_layout(zf.read(_member(zf, PROC_LAYOUT)).decode(ENCODING))
        text = zf.read(_member(zf, PROC_FILE)).decode(ENCODING)
    raw = parse_fixed_width(text, layout)
    return procedures_frame(raw, group_prefix)


def procedures_frame(raw: pl.DataFrame, group_prefix: str = "07") -> pl.DataFrame:
    cents = {c: pl.col(c).cast(pl.Int64, strict=False) / 100 for c in ("VL_SH", "VL_SA", "VL_SP")}
    return (
        raw.filter(pl.col("CO_PROCEDIMENTO").str.starts_with(group_prefix))
        .with_columns(**cents)
        .select(
            pl.col("CO_PROCEDIMENTO").alias("codigo_sigtap"),
            pl.col("NO_PROCEDIMENTO").alias("descricao_sigtap"),
            pl.col("VL_SH").alias("valor_sh"),
            pl.col("VL_SA").alias("valor_sa"),
            pl.col("VL_SP").alias("valor_sp"),
            pl.col("CO_FINANCIAMENTO").alias("co_financiamento"),
            pl.col("DT_COMPETENCIA").alias("competencia"),
        )
    )


# ---------------------------------------------------------- seleção de ZIPs ----
def parse_listing(names: list[str]) -> pl.DataFrame:
    rows = []
    for n in names:
        m = ZIP_RE.match(n.strip().split("/")[-1])
        if m:
            rows.append({"arquivo": m.group(0), "competencia": m.group(1), "versao": m.group(2)})
    return pl.DataFrame(
        rows, schema={"arquivo": pl.String, "competencia": pl.String, "versao": pl.String}
    )


def select_competences(listing: pl.DataFrame, start_year: int, month: int = 1) -> pl.DataFrame:
    """Uma competência por ano desde `start_year` (o mês `month`, ou o primeiro disponível no
    ano) + a mais recente. Para cada competência, a versão mais nova do arquivo."""
    if listing.height == 0:
        return listing
    latest_version = (
        listing.sort(["competencia", "versao"]).group_by("competencia", maintain_order=True).last()
    )
    df = latest_version.with_columns(
        pl.col("competencia").str.slice(0, 4).cast(pl.Int32).alias("_ano"),
        pl.col("competencia").str.slice(4, 2).cast(pl.Int32).alias("_mes"),
    ).filter(pl.col("_ano") >= start_year)
    yearly = (
        df.with_columns((pl.col("_mes") - month).abs().alias("_dist"))
        .sort(["_ano", "_dist", "_mes"])
        .group_by("_ano", maintain_order=True)
        .first()
    )
    latest = df.sort("competencia").tail(1)
    out = pl.concat([yearly.select(listing.columns), latest.select(listing.columns)])
    return out.unique(subset=["competencia"], keep="first").sort("competencia")


# ------------------------------------------------------------------- FTP ----
_FTP_ERRORS = (*ftplib.all_errors, TimeoutError)


class FtpSource:
    """Acesso ao FTP público do DATASUS (anônimo, sem cadastro), com retry e timeout."""

    def __init__(self, settings: Settings):
        cfg = settings.complementary.sigtap
        self.host = cfg["ftp_host"]
        self.dir = cfg["ftp_dir"]
        self.timeout = settings.http.timeout_s
        self.attempts = settings.http.max_attempts

    def url(self, name: str) -> str:
        return f"ftp://{self.host}{self.dir.rstrip('/')}/{name}"

    def _retry(self):
        return retry(
            retry=retry_if_exception_type(_FTP_ERRORS),
            stop=stop_after_attempt(self.attempts),
            wait=wait_exponential_jitter(initial=2, max=60),
            reraise=True,
        )

    def _connect(self) -> ftplib.FTP:
        ftp = ftplib.FTP(self.host, timeout=self.timeout)
        ftp.login()  # anônimo
        ftp.cwd(self.dir)
        return ftp

    def list_names(self) -> list[str]:
        @self._retry()
        def go() -> list[str]:
            with self._connect() as ftp:
                return ftp.nlst()

        return go()

    def download(self, name: str, dest: Path) -> Path:
        @self._retry()
        def go() -> Path:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(dest.suffix + ".part")
            with self._connect() as ftp, tmp.open("wb") as fh:
                ftp.retrbinary(f"RETR {name}", fh.write, blocksize=1 << 20)
            tmp.replace(dest)
            return dest

        return go()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- ingest ----
def ingest(settings: Settings, client: HttpClient) -> dict[str, Any]:
    """Lista as competências, baixa as escolhidas (cache por arquivo) e grava a bronze."""
    cfg = settings.complementary.sigtap
    store = client.store
    ftp = FtpSource(settings)

    if store.exists(LISTING_KEY) and not client.force:
        names = store.read(LISTING_KEY)["body"]["arquivos"]
        client.stats["cache"] += 1
    elif client.offline:
        logger.warning("SIGTAP offline: sem listagem em {}", store.dir)
        return {"competencias": 0}
    else:
        names = sorted(ftp.list_names())
        client.stats["network"] += 1
        store.write(
            LISTING_KEY,
            {
                "meta": {
                    "url": ftp.url(""),
                    "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                    "n_arquivos": len(names),
                },
                "body": {"arquivos": names},
            },
        )

    chosen = select_competences(
        parse_listing(names), int(cfg.get("start_year", 2015)), int(cfg.get("month", 1))
    )
    frames, fetched = [], []
    for r in chosen.iter_rows(named=True):
        dest = store.dir / r["arquivo"]
        key = f"zip_{r['competencia']}"
        if not dest.exists() or client.force:
            if client.offline:
                logger.warning("SIGTAP offline: {} ausente nas fixtures", r["arquivo"])
                continue
            try:
                ftp.download(r["arquivo"], dest)
                client.stats["network"] += 1
            except _FTP_ERRORS as exc:
                client.stats["failed"] += 1
                logger.error("SIGTAP: falha ao baixar {}: {!r}", ftp.url(r["arquivo"]), exc)
                continue
            store.write(
                key,
                {
                    "meta": {
                        "url": ftp.url(r["arquivo"]),
                        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "sha256": _sha256(dest),
                        "bytes": dest.stat().st_size,
                    },
                    "body": {"arquivo": r["arquivo"], "competencia": r["competencia"]},
                },
            )
        else:
            client.stats["cache"] += 1
        meta = store.read(key)["meta"] if store.exists(key) else {}
        fetched.append(meta.get("fetched_at"))
        try:
            df = read_procedures(dest, cfg.get("group_prefix", "07"))
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            client.stats["failed"] += 1
            logger.error("SIGTAP: {} ilegível: {!r}", r["arquivo"], exc)
            continue
        frames.append(df.with_columns(pl.lit(r["arquivo"]).alias("arquivo")))

    if not frames:
        return {"competencias": 0}
    out = pl.concat(frames, how="vertical")
    last = max((f for f in fetched if f), default=None)
    write_bronze(settings, TABLE, client.snapshot, out, SOURCE, last)
    comps = out["competencia"].unique().sort().to_list()
    logger.info(
        "SIGTAP: {} competências ({}…{}), {} linhas", len(comps), comps[0], comps[-1], out.height
    )
    return {"competencias": len(comps), "linhas_grupo_07": out.height}


# ---------------------------------------------------------------- silver ----
def competence_month(comp: str) -> date:
    return date(int(comp[:4]), int(comp[4:6]), 1)


def silver(bronze: pl.DataFrame, index: pl.DataFrame) -> pl.DataFrame:
    """Uma linha por (competência, procedimento), com valor de OPME (VL_SH) nominal e real."""
    from raiox.transform.deflate import deflate

    df = (
        bronze.sort("_snapshot")
        .unique(subset=["competencia", "codigo_sigtap"], keep="last")
        .with_columns(
            pl.col("competencia")
            .map_elements(competence_month, return_dtype=pl.Date)
            .alias("mes_competencia"),
            pl.col("valor_sh").alias("valor_opme"),
        )
        .select(
            "codigo_sigtap",
            "descricao_sigtap",
            "competencia",
            "mes_competencia",
            "valor_opme",
            "valor_sa",
            "co_financiamento",
        )
        .sort(["codigo_sigtap", "competencia"])
    )
    return deflate(df, "mes_competencia", ["valor_opme"], index)
