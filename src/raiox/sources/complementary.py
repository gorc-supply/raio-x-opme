"""Despacho das fontes complementares (Fase 5.6), cada uma atrás de um flag."""

from __future__ import annotations

from typing import Any

from raiox.config import Settings
from raiox.http import HttpClient
from raiox.logs import logger
from raiox.state import mark_run, resolve_snapshot


def enabled(settings: Settings) -> list[str]:
    c = settings.complementary
    return [name for name in ("anvisa", "bps", "pncp_itens") if getattr(c, name).get("enabled")]


def ingest(settings: Settings, force: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in enabled(settings):
        source = "pncp" if name == "pncp_itens" else name
        snap = resolve_snapshot(settings, source, force)
        try:
            with HttpClient(settings, source, snapshot=snap, force=force) as client:
                if name == "anvisa":
                    from raiox.sources import anvisa as mod
                elif name == "bps":
                    from raiox.sources import bps as mod
                else:
                    from raiox.sources import pncp as mod
                out[name] = mod.ingest(settings, client)
                if snap:
                    mark_run(settings, source, client.snapshot, complete=client.stats["failed"] == 0)
        except Exception as exc:  # noqa: BLE001 — complementar nunca derruba o pipeline
            logger.exception("Fonte complementar {} falhou: {!r}", name, exc)
            out[name] = {"error": repr(exc)}
    if not out:
        logger.info("Nenhuma fonte complementar habilitada em settings.yaml.")
    return out
