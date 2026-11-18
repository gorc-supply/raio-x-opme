"""Estado de execução: snapshot em andamento por fonte (permite retomar ingestões).

Se uma ingestão cai no meio, o arquivo data/state/<fonte>_run.json fica com
complete=false. A próxima execução reutiliza o MESMO snapshot, e as páginas já
baixadas vêm do cache do raw: a ingestão continua de onde parou, mesmo em outro dia.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from raiox.config import Settings
from raiox.logs import logger


def _state_file(settings: Settings, name: str) -> Path:
    return settings.path("state") / f"{name}.json"


def read_state(settings: Settings, name: str) -> dict[str, Any] | None:
    path = _state_file(settings, name)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_state(settings: Settings, name: str, data: dict[str, Any]) -> None:
    path = _state_file(settings, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {**data, "updated_at": datetime.now(UTC).isoformat(timespec="seconds")}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_snapshot(settings: Settings, source: str, force: bool = False) -> str | None:
    """Snapshot a usar numa ingestão. None no modo offline (o cliente escolhe a fixture)."""
    if settings.offline:
        return None
    today = date.today().isoformat()
    raw_dir = settings.path("raw") / source
    if force:
        snap, i = today, 1
        while (raw_dir / snap).exists():
            snap = f"{today}_{i}"
            i += 1
        return snap
    st = read_state(settings, f"{source}_run")
    if st and not st.get("complete") and st.get("snapshot"):
        logger.info("Retomando ingestão de {} no snapshot {}", source, st["snapshot"])
        return st["snapshot"]
    return today


def mark_run(settings: Settings, source: str, snapshot: str, complete: bool, **extra: Any) -> None:
    if settings.offline:
        return
    write_state(settings, f"{source}_run", {"snapshot": snapshot, "complete": complete, **extra})
