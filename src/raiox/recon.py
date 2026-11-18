"""Fase 1 — reconhecimento das fontes.

Faz uma chamada real mínima a cada fonte do núcleo, mede latência, registra
campos e tipos, descobre cobertura temporal e salva amostras em data/fixtures/recon/.
O resultado consolidado vai para data/reference/recon.json (base de docs/FONTES.md).
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import date
from typing import Any

from raiox.config import HttpCfg, Settings
from raiox.http import HttpClient
from raiox.logs import logger
from raiox.sources.compras import EXPECTED_PRICE_FIELDS, ComprasSource

SAMPLE_ITEM = 476779  # stent coronário farmacológico 3,5 × até 40 mm (Fase 1)
SAMPLE_NCM = "90219012"


def _types(record: dict[str, Any]) -> dict[str, str]:
    return {k: type(v).__name__ for k, v in record.items()}


def _save_fixture(settings: Settings, name: str, payload: Any, max_rows: int = 5) -> None:
    out = settings.path("fixtures") / "recon"
    out.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, dict) and isinstance(payload.get("resultado"), list):
        payload = {**payload, "resultado": payload["resultado"][:max_rows]}
    elif (
        isinstance(payload, dict)
        and isinstance(payload.get("data"), dict)
        and isinstance(payload["data"].get("list"), list)
    ):
        payload = {
            **payload,
            "data": {**payload["data"], "list": payload["data"]["list"][:max_rows]},
        }
    elif isinstance(payload, list):
        payload = payload[:max_rows]
    (out / f"{name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def _timed(fn, *a, **k):
    t0 = time.perf_counter()
    r = fn(*a, **k)
    return r, round(time.perf_counter() - t0, 2)


def run_recon(settings: Settings) -> dict[str, Any]:
    report: dict[str, Any] = {"date": date.today().isoformat()}

    # ---------------------------------------------------------- Compras ----
    with HttpClient(settings, "recon_compras") as c:
        src = ComprasSource(settings, c)
        r: dict[str, Any] = {}
        env, dt = _timed(c.get_json, src.url(settings.compras.openapi_path), "openapi")
        if env:
            (settings.path("reference") / "compras_openapi.json").write_text(
                json.dumps(env["body"], ensure_ascii=False), encoding="utf-8"
            )
            r["openapi_paths"] = len(env["body"]["paths"])
        paths = {}
        for p in settings.compras.price_path_candidates:
            e = c.get_json(
                src.url(p),
                key=f"path_{p.strip('/').split('/')[0]}",
                params={
                    "pagina": 1,
                    "tamanhoPagina": 10,
                    "tipo": "codigoItemCatalogo",
                    "codigo": SAMPLE_ITEM,
                },
            )
            paths[p] = "ok" if e else "falhou (404)"
        r["price_path_candidates"] = paths

        rows: list[dict[str, Any]] = []
        lat = []
        for env in c.paginate(
            src.url(settings.compras.price_path_candidates[0]),
            {"tipo": "codigoItemCatalogo", "codigo": SAMPLE_ITEM},
            f"preco_{SAMPLE_ITEM}",
            settings.compras.page_size,
        ):
            lat.append(env["meta"]["elapsed_s"])
            rows.extend(env["body"]["resultado"])
            if len(rows) <= settings.compras.page_size:
                _save_fixture(settings, "compras_preco_material", env["body"])
        if rows:
            dates = sorted(x["dataCompra"] for x in rows if x.get("dataCompra"))
            r["price_sample"] = {
                "item": SAMPLE_ITEM,
                "registros": len(rows),
                "latencia_s": lat,
                "data_compra_min": dates[0],
                "data_compra_max": dates[-1],
                "campos": _types(rows[0]),
                "campos_ausentes_vs_esperado": sorted(EXPECTED_PRICE_FIELDS - set(rows[0])),
                "ufs": sorted({x["estado"] for x in rows if x.get("estado")}),
            }
        e, dt = _timed(
            c.get_json,
            src.url(settings.compras.detail_path),
            "detalhe",
            {"pagina": 1, "tamanhoPagina": 10, "codigoItemCatalogo": SAMPLE_ITEM},
        )
        if e:
            _save_fixture(settings, "compras_preco_detalhe", e["body"])
            res = e["body"].get("resultado", [])
            r["detail"] = {
                "latencia_s": dt,
                "campos": _types(res[0]) if res else {},
                "total": e["body"].get("totalRegistros"),
            }
        e, dt = _timed(
            c.get_json,
            src.url(settings.compras.catalog_item_path),
            "catmat_ncm",
            {"pagina": 1, "tamanhoPagina": 500, "codigo_ncm": SAMPLE_NCM},
        )
        if e:
            _save_fixture(settings, "catmat_item_por_ncm", e["body"])
            res = e["body"]["resultado"]
            r["catmat_por_ncm"] = {
                "ncm": SAMPLE_NCM,
                "latencia_s": dt,
                "total": e["body"]["totalRegistros"],
                "campos": _types(res[0]) if res else {},
                "formato_com_pontos_funciona": False,
            }
            e2 = c.get_json(
                src.url(settings.compras.catalog_item_path),
                "catmat_ncm_pontos",
                {"pagina": 1, "tamanhoPagina": 10, "codigo_ncm": "9021.90.12"},
            )
            if e2 and e2["body"].get("totalRegistros"):
                r["catmat_por_ncm"]["formato_com_pontos_funciona"] = True
        e = c.get_json(
            src.url(settings.compras.catalog_item_path),
            "catmat_desc",
            {"pagina": 1, "tamanhoPagina": 10, "descricaoItem": "STENT"},
        )
        r["catmat_busca_descricao_substring"] = bool(e and e["body"].get("totalRegistros"))
        report["compras"] = r

    # PNCP 14.133 (itens por código de catálogo): poucas tentativas, é complementar.
    fast = settings.model_copy(
        update={"http": HttpCfg(**{**settings.http.model_dump(), "max_attempts": 2})}
    )
    with HttpClient(fast, "recon_pncp") as c:
        src = ComprasSource(fast, c)
        e, dt = _timed(
            c.get_json,
            src.url(settings.compras.pncp_items_path),
            "pncp_itens",
            {
                "pagina": 1,
                "tamanhoPagina": 10,
                "codItemCatalogo": SAMPLE_ITEM,
                "dataInclusaoPncpInicial": "2025-09-01",
                "dataInclusaoPncpFinal": "2025-09-30",
            },
        )
        report["pncp_itens"] = {"ok": e is not None, "latencia_s": dt}
        if e:
            _save_fixture(settings, "pncp_itens", e["body"])

    # -------------------------------------------------------- ComexStat ----
    with HttpClient(settings, "recon_comex") as c:
        base = settings.comex.base_url
        r = {}
        for name, path in {
            "filters": "/general/filters",
            "details": "/general/details",
            "metrics": "/general/metrics",
            "dates_updated": "/general/dates/updated",
        }.items():
            e, dt = _timed(c.get_json, base + path, f"aux_{name}")
            r[name] = {"latencia_s": dt, "ok": e is not None}
            if e and name == "dates_updated":
                r["ultima_atualizacao"] = e["body"]["data"]
            if e and name == "metrics":
                r["metricas"] = [m["id"] for m in e["body"]["data"]["list"]]
        e, dt = _timed(c.get_json, base + "/tables/ncm", "aux_ncm")
        if e:
            table = {x["coNcm"]: x for x in e["body"]["data"]["list"]}
            r["ncm_validacao"] = {
                n.ncm: {
                    "existe": n.ncm in table,
                    "descricao": table.get(n.ncm, {}).get("noNCM"),
                    "unidade_estatistica": table.get(n.ncm, {}).get("unit"),
                }
                for n in settings.comex.ncms
            }
        body = {
            "flow": "import",
            "monthDetail": True,
            "period": {"from": "2024-01", "to": "2024-12"},
            "filters": [{"filter": "ncm", "values": [SAMPLE_NCM]}],
            "details": ["ncm", "country", "state"],
            "metrics": settings.comex.metrics_import,
        }
        e, dt = _timed(c.post_json, base + "/general", "general_sample", body)
        if e:
            _save_fixture(settings, "comex_general_import", e["body"], max_rows=10)
            lst = e["body"]["data"]["list"]
            r["general_sample"] = {
                "latencia_s": dt,
                "linhas": len(lst),
                "campos": _types(lst[0]) if lst else {},
            }
        # Cobertura: ano mais antigo com dados para o NCM de amostra.
        body_y = {
            **body,
            "monthDetail": False,
            "period": {"from": "1997-01", "to": "2026-12"},
            "details": ["ncm"],
            "metrics": ["metricFOB"],
        }
        e = c.post_json(base + "/general", "general_years", body_y)
        if e:
            years = sorted(int(x["year"]) for x in e["body"]["data"]["list"])
            r["cobertura_anos_ncm_amostra"] = [years[0], years[-1]] if years else None
        report["comex"] = r

    # -------------------------------------------------------------- BCB ----
    with HttpClient(settings, "recon_bcb") as c:
        r = {}
        url = settings.bcb.base_url
        for code in (settings.bcb.ipca_series, settings.bcb.fx_series):
            e, dt = _timed(
                c.get_json,
                url.format(code=code),
                f"sgs_{code}",
                {"formato": "json", "dataInicial": "01/01/2025", "dataFinal": "31/12/2025"},
            )
            if e:
                _save_fixture(settings, f"bcb_sgs_{code}", e["body"], max_rows=12)
                r[str(code)] = {"latencia_s": dt, "n_2025": len(e["body"]), "exemplo": e["body"][0]}
        # Checagem: 3698 (média mensal venda) ≈ média da série diária 1 no mesmo mês.
        e1 = c.get_json(
            url.format(code=1),
            "sgs_1_2025_09",
            {"formato": "json", "dataInicial": "01/09/2025", "dataFinal": "30/09/2025"},
        )
        e2 = c.get_json(
            url.format(code=settings.bcb.fx_series),
            "sgs_fx_2025_09",
            {"formato": "json", "dataInicial": "01/09/2025", "dataFinal": "30/09/2025"},
        )
        if e1 and e2:
            daily = statistics.mean(float(x["valor"]) for x in e1["body"])
            monthly = float(e2["body"][0]["valor"])
            r["checagem_cambio_set2025"] = {
                "media_serie_1": round(daily, 4),
                "serie_3698": monthly,
                "diferenca": round(monthly - daily, 4),
            }
        # Limite de janela de séries diárias.
        e = c.get_json(
            url.format(code=1),
            "sgs_1_janela_longa",
            {"formato": "json", "dataInicial": "01/01/2010", "dataFinal": "31/12/2025"},
        )
        r["serie_diaria_janela_16_anos_ok"] = e is not None
        report["bcb"] = r

    # ------------------------------------------------------------- IBGE ----
    with HttpClient(settings, "recon_ibge") as c:
        r = {}
        e, dt = _timed(c.get_json, settings.ibge.states_url, "estados")
        if e:
            _save_fixture(settings, "ibge_estados", e["body"], max_rows=27)
            r["estados"] = {"latencia_s": dt, "n": len(e["body"]), "campos": _types(e["body"][0])}
        e, dt = _timed(c.get_json, settings.ibge.geojson_url, "malha")
        if e:
            r["malha"] = {
                "latencia_s": dt,
                "bytes": e["meta"]["bytes"],
                "features": len(e["body"]["features"]),
                "propriedades": list(e["body"]["features"][0]["properties"]),
            }
        report["ibge"] = r

    out = settings.path("reference") / "recon.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("Reconhecimento salvo em {}", out)
    return report
