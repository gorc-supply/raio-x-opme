"""Fixtures: amostras reais e pequenas do raw, para testes e modo offline.

`uv run raiox fixtures build` copia do snapshot mais recente de cada fonte um
subconjunto pequeno (mesmo formato de envelope do raw) para
data/fixtures/raw/<fonte>/<snapshot>/. Respostas grandes são recortadas
(campo meta.fixture_recortada = true), sem alterar nenhum valor.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from raiox.config import Settings
from raiox.http import list_snapshots, safe_key
from raiox.logs import logger

# Itens escolhidos por cobrirem famílias diferentes e várias UFs elegíveis.
FIXTURE_ITEMS = [616180, 443802, 436621, 476772, 480767, 614825]
FIXTURE_NCMS = ["90215000", "90219012", "90211020"]
FIXTURE_COMEX_YEARS = [2025]
ANVISA_MAX_LINES_PER_FAMILY = 80


def _latest(settings: Settings, source: str) -> Path | None:
    raw = settings.root / settings.paths.raw
    snaps = list_snapshots(raw, source)
    return raw / source / snaps[-1] if snaps else None


def _copy(src: Path, dst_dir: Path) -> int:
    dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst_dir / src.name)
    return src.stat().st_size


def build_fixtures(settings: Settings) -> dict[str, int]:
    out_root = settings.root / settings.paths.fixtures / "raw"
    if out_root.exists():
        shutil.rmtree(out_root)
    sizes: dict[str, int] = {}

    # Compras: páginas de preço + ficha CATMAT dos itens de fixture.
    snap = _latest(settings, "compras")
    if snap:
        dst = out_root / "compras" / snap.name
        total = 0
        from raiox.transform.normalize import is_cpf, mask_cpf

        for code in FIXTURE_ITEMS:
            files = sorted(snap.glob(f"{safe_key(f'preco_item_{code}_')}*.json"))
            windowed = [f for f in files if "_w" in f.stem]
            # Item coletado por janelas: a sondagem só é usada para descobrir o total.
            probe = [f for f in files if f.stem.endswith(f"{code}_p0001")]
            for p in windowed + probe if windowed else files:
                # LGPD: fixtures são versionadas; CPF de pessoa física sai mascarado.
                env = json.loads(p.read_text(encoding="utf-8"))
                for r in env["body"].get("resultado", []):
                    if is_cpf(r.get("niFornecedor")):
                        r["niFornecedor"] = mask_cpf(r["niFornecedor"])
                        r["nomeFornecedor"] = "PESSOA FISICA"
                dst.mkdir(parents=True, exist_ok=True)
                (dst / p.name).write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
                total += (dst / p.name).stat().st_size
            for p in sorted(snap.glob(f"{safe_key(f'catalogo_item_{code}_')}*.json")):
                total += _copy(p, dst)
        sizes["compras"] = total

    # ComexStat: um ano, NCMs selecionados (recorte das linhas, valores intactos).
    snap = _latest(settings, "comex")
    if snap:
        dst = out_root / "comex" / snap.name
        dst.mkdir(parents=True, exist_ok=True)
        total = _copy(snap / "aux_dates_updated.json", dst)
        for flow in ("import", "export"):
            for year in FIXTURE_COMEX_YEARS:
                for p in sorted(snap.glob(f"general_{flow}_{year}_c*.json")):
                    env = json.loads(p.read_text(encoding="utf-8"))
                    lst = env["body"]["data"]["list"]
                    env["body"]["data"]["list"] = [r for r in lst if r.get("coNcm") in FIXTURE_NCMS]
                    env["meta"]["fixture_recortada"] = True
                    target = dst / p.name
                    target.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")
                    total += target.stat().st_size
        sizes["comex"] = total

    # BCB e IBGE: pequenos, copiados inteiros.
    for source in ("bcb", "ibge"):
        snap = _latest(settings, source)
        if snap:
            dst = out_root / source / snap.name
            sizes[source] = sum(_copy(p, dst) for p in sorted(snap.glob("*.json")))

    # ANVISA: cabeçalho + amostra de linhas OPME por família (latin-1, como a fonte).
    snap = _latest(settings, "anvisa")
    if snap and (snap / "TA_PRODUTO_SAUDE_SITE.csv").exists():
        from raiox.sources.anvisa import FILE, classify, read_csv

        df = classify(read_csv(snap / FILE))
        import polars as pl

        sample = (
            df.with_columns(pl.int_range(pl.len()).over("familia_macro").alias("_i"))
            .filter(pl.col("_i") < ANVISA_MAX_LINES_PER_FAMILY)
            .drop("_i", "familia_macro")
        )
        dst = out_root / "anvisa" / snap.name
        dst.mkdir(parents=True, exist_ok=True)
        text = sample.write_csv(separator=";", quote_style="never")
        (dst / FILE).write_bytes(text.encode("latin1", errors="replace"))
        sizes["anvisa"] = (dst / FILE).stat().st_size

    manifest = {
        "itens_catmat": FIXTURE_ITEMS,
        "ncms": FIXTURE_NCMS,
        "anos_comex": FIXTURE_COMEX_YEARS,
        "bytes_por_fonte": sizes,
    }
    (settings.root / settings.paths.fixtures / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    logger.info("Fixtures geradas: {} (total {:.1f} MB)", sizes, sum(sizes.values()) / 1e6)
    return sizes
