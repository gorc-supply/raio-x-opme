"""Configuração de logs com loguru: console + arquivo rotativo em logs/."""

from __future__ import annotations

import sys

from loguru import logger

from raiox.config import Settings

_configured = False


def setup_logging(settings: Settings, level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
    )
    log_dir = settings.root / settings.paths.logs
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "raiox_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
        enqueue=False,
    )
    _configured = True


__all__ = ["logger", "setup_logging"]
