"""Explicit failure recording.

The scout must never fill a gap with a guess. When a source errors, returns
nothing, or is unavailable, the reason is recorded here and surfaced in both
output files.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .models import Failure

log = logging.getLogger("scout")


class FailureLog:
    def __init__(self) -> None:
        self._items: list[Failure] = []

    def record(self, source: str, target: str, stage: str, error: str) -> Failure:
        failure = Failure(
            source=source,
            target=target,
            stage=stage,
            error=str(error)[:800],
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self._items.append(failure)
        log.warning("SOURCE FAILURE [%s] %s (%s): %s", source, target, stage, failure.error)
        return failure

    @property
    def items(self) -> list[Failure]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def to_list(self) -> list[dict]:
        return [f.to_dict() for f in self._items]
