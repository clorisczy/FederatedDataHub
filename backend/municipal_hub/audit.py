from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock

from municipal_hub.schema import AuditEntry

_lock = Lock()
_log: list[AuditEntry] = []


def record(*, role: str, action: str, resource: str, detail: str | None = None) -> None:
    entry = AuditEntry(
        ts=datetime.now(timezone.utc).isoformat(),
        role=role,
        action=action,
        resource=resource,
        detail=detail,
    )
    with _lock:
        _log.append(entry)
        if len(_log) > 500:
            del _log[:-500]


def recent(limit: int = 50) -> list[AuditEntry]:
    with _lock:
        return list(_log[-limit:])
