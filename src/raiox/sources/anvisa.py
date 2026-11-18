"""ANVISA — produtos para saúde registrados (dados abertos, sem autenticação).

Arquivo: https://dados.anvisa.gov.br/dados/TA_PRODUTO_SAUDE_SITE.csv (~28 MB,
separador ';', latin-1, sem aspas confiáveis). Uma linha por registro × fabricante.
Uso: proporção de registros vigentes cujo(s) fabricante(s) é(são) estrangeiro(s),
por família — proxy de dependência tecnológica (não mede volume de vendas).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

from raiox.bronze import write_bronze
from raiox.config import Settings
from raiox.http import HttpClient
from raiox.logs import logger

SOURCE = "anvisa"
FILE = "TA_PRODUTO_SAUDE_SITE.csv"

# (família macro, regex sobre NOME_TECNICO em maiúsculas, regex de exclusão)
FAMILY_PATTERNS: list[tuple[str, str, str | None]] = [
    ("Stents", r"STENT.*(CORON|ART[EÉ]RIAS PERIF|CAR[OÓ]TID)", None),
    (
        "Próteses articulares",
        r"(PR[OÓ]TESES? TOTA(L|IS) D[OE] (QUADRIL|JOELHO)|ARTROPLASTIA DE (QUADRIL|JOELHO)|ARTICULA[CÇ][AÃ]O DE JOELHO)",
        None,
    ),
    (
        "Placas, parafusos e hastes",
        r"(PARAFUSO [OÓ]SSEO ORTOP|PARAFUSO N[AÃ]O ABSORV[IÍ]VEL PARA OSTEOSS|PLACA.*OSTEOSS|HASTES [OÓ]SSEAS|HASTE INTRAMEDULAR)",
        None,
    ),
    ("Marca-passos", r"MARCA-PASSO (CARD[IÍ]ACO IMPLANT|IMPLANT|INTRACARD)", None),
    ("Válvulas cardíacas", r"(V[AÁ]LVULA CARD|PR[OÓ]TESE VALV|BIOPR[OÓ]TESE)", r"MEDIDOR"),
    ("Cateteres", r"CATETER BAL[AÃ]O PARA ANGIOPLASTIA CORON", None),
    ("Próteses vasculares", r"ENDOPR[OÓ]TESE.*VASCULAR|ENDOPR[OÓ]TESE \(VASCULAR\)", None),
]


def read_csv(path: Path) -> pl.DataFrame:
    return pl.read_csv(
        path,
        separator=";",
        encoding="latin1",
        infer_schema=False,
        quote_char=None,
        truncate_ragged_lines=True,
    )


def classify(df: pl.DataFrame) -> pl.DataFrame:
    up = pl.col("NOME_TECNICO").str.to_uppercase()
    expr = pl.lit(None, dtype=pl.String)
    for fam, pat, excl in reversed(FAMILY_PATTERNS):
        cond = up.str.contains(pat)
        if excl:
            cond = cond & ~up.str.contains(excl)
        expr = pl.when(cond).then(pl.lit(fam)).otherwise(expr)
    return df.with_columns(expr.alias("familia_macro")).filter(
        pl.col("familia_macro").is_not_null()
    )


def ingest(settings: Settings, client: HttpClient) -> dict[str, int]:
    url = settings.complementary.anvisa.get("base_url", "https://dados.anvisa.gov.br/dados/") + FILE
    dest = client.store.dir / FILE
    path = client.download(url, dest)
    if path is None:
        logger.error("ANVISA: download falhou ({})", url)
        return {"registros": 0}
    df = classify(read_csv(path))
    write_bronze(settings, "anvisa_produtos", client.snapshot, df, SOURCE, date.today().isoformat())
    return {"linhas_opme": df.height}


def silver(bronze: pl.DataFrame, ref_date: date) -> pl.DataFrame:
    val = pl.col("VALIDADE_REGISTRO_CADASTRO")
    exp = val.str.strptime(pl.Date, "%d/%m/%Y", strict=False)
    return (
        bronze.sort("_snapshot")
        .with_columns(
            ((val == "VIGENTE") | (exp >= ref_date)).fill_null(False).alias("vigente"),
            pl.col("NOME_PAIS_FABRIC")
            .str.strip_chars()
            .str.to_uppercase()
            .alias("pais_fabricante"),
        )
        .select(
            pl.col("NUMERO_REGISTRO_CADASTRO").alias("registro"),
            pl.col("NOME_TECNICO").alias("nome_tecnico"),
            pl.col("CLASSE_RISCO").alias("classe_risco"),
            pl.col("DETENTOR_REGISTRO_CADASTRO").alias("detentor"),
            pl.col("NOME_FABRICANTE").alias("fabricante"),
            "pais_fabricante",
            "familia_macro",
            "vigente",
            pl.col("_snapshot").alias("snapshot"),
        )
        .unique(subset=["registro", "fabricante", "pais_fabricante"], keep="last")
    )


def gold_by_family(sv: pl.DataFrame) -> pl.DataFrame:
    """Por família: registros vigentes, % só com fabricante estrangeiro, principais países."""
    v = sv.filter(
        pl.col("vigente")
        & pl.col("pais_fabricante").is_not_null()
        & (pl.col("pais_fabricante") != "")
    )
    reg = v.group_by(["familia_macro", "registro"], maintain_order=True).agg(
        (pl.col("pais_fabricante") != "BRASIL").all().alias("so_estrangeiro"),
        (pl.col("pais_fabricante") == "BRASIL").any().alias("tem_nacional"),
    )
    fam = reg.group_by("familia_macro", maintain_order=True).agg(
        pl.len().cast(pl.Int64).alias("registros_vigentes"),
        pl.col("so_estrangeiro").mean().alias("share_so_estrangeiro"),
        pl.col("tem_nacional").mean().alias("share_com_fabricante_nacional"),
    )
    countries = (
        v.unique(subset=["familia_macro", "registro", "pais_fabricante"])
        .group_by(["familia_macro", "pais_fabricante"], maintain_order=True)
        .len()
        .with_columns((pl.col("len") / pl.col("len").sum().over("familia_macro")).alias("share"))
        .sort(["familia_macro", "len", "pais_fabricante"], descending=[False, True, False])
        .group_by("familia_macro", maintain_order=True)
        .agg(
            pl.concat_str(
                [
                    pl.col("pais_fabricante"),
                    pl.lit(" ("),
                    (pl.col("share") * 100).round(0).cast(pl.Int64).cast(pl.String),
                    pl.lit("%)"),
                ]
            )
            .head(4)
            .str.join(", ")
            .alias("principais_paises_fabricantes")
        )
    )
    return fam.join(countries, on="familia_macro", how="left").sort(
        "share_so_estrangeiro", descending=True
    )
