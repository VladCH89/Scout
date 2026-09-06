"""Minimal HTTP helper with a real User-Agent and bounded retries."""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger("scout")

RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    pass


def get_json(
    url: str,
    *,
    user_agent: str,
    params: dict[str, Any] | None = None,
    timeout: float = 30.0,
    attempts: int = 4,
    backoff: float = 2.0,
) -> Any:
    """GET ``url`` and return parsed JSON, or raise HttpError.

    Retries on transient statuses with exponential backoff. Any failure that
    survives the retries is raised so the caller can record it explicitly.
    """
    last: str = "no attempt made"
    for attempt in range(attempts):
        try:
            resp = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers={"User-Agent": user_agent, "Accept": "application/json"},
            )
        except requests.RequestException as exc:  # network-level
            last = f"{type(exc).__name__}: {exc}"
        else:
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError as exc:
                    raise HttpError(f"non-JSON response from {url}: {exc}") from exc
            last = f"HTTP {resp.status_code}"
            if resp.status_code not in RETRY_STATUS:
                raise HttpError(f"{last} from {url}")
        if attempt < attempts - 1:
            delay = backoff * (2**attempt)
            log.info("retrying %s in %.1fs (%s)", url, delay, last)
            time.sleep(delay)
    raise HttpError(f"{last} from {url} after {attempts} attempts")
