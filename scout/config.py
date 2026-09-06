"""Configuration loading.

Defaults live here; ``config.json`` in the repo root (or any path passed with
``--config``) overrides them key by key.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    # --- Reddit ---------------------------------------------------------
    "subreddits": [
        "SomebodyMakeThis",
        "AppIdeas",
        "productivity",
        "personalfinance",
        "frugal",
        "smallbusiness",
        "Entrepreneur",
    ],
    "demand_phrases": [
        "is there an app",
        "why is there no",
        "wish there was",
        "does anyone know a tool",
        "I'd pay for",
    ],
    # Reddit search window: hour | day | week | month | year | all
    "reddit_timeframe": "year",
    "reddit_limit_per_query": 100,
    "reddit_request_delay_seconds": 1.5,
    "reddit_user_agent": "product-opportunity-scout/1.0 (+https://github.com/VladCH89/Scout)",

    # --- Google Trends --------------------------------------------------
    "trends_enabled": True,
    "trends_timeframe": "today 12-m",
    "trends_geo": "",
    "trends_max_topics": 15,
    "trends_request_delay_seconds": 4.0,
    # Percentage change between the first and last 3-month window that counts
    # as a direction rather than noise.
    "trends_direction_threshold_pct": 10.0,

    # --- App stores -----------------------------------------------------
    "appstore_enabled": True,
    "appstore_max_topics": 10,
    "appstore_apps_per_topic": 3,
    "appstore_reviews_per_app": 100,
    "appstore_country": "us",
    "appstore_request_delay_seconds": 1.0,
    # Only 1- and 2-star reviews are read.
    "appstore_max_rating": 2,
    "missing_feature_patterns": [
        "no way to",
        "there is no way",
        "there's no way",
        "doesn't have",
        "does not have",
        "don't have a way",
        "no option to",
        "missing feature",
        "is missing",
        "lacks",
        "wish it had",
        "wish there was",
        "would be great if",
        "should have",
        "needs a way",
        "can't even",
        "cannot even",
        "used to have",
        "no support for",
        "not supported",
    ],

    # --- Clustering & scoring ------------------------------------------
    "cluster_similarity_threshold": 0.08,
    "min_independent_sources": 2,
    "max_topics_in_report": 40,
    "trend_adjustment": {"rising": 0.25, "flat": 0.0, "falling": -0.20, "unknown": 0.0},
    "complaint_adjustment_cap": 0.50,
    "complaint_adjustment_weight": 0.35,

    # --- Output ---------------------------------------------------------
    "output_dir": "findings",
}


def load_config(path: str | Path | None) -> dict[str, Any]:
    """Return DEFAULTS overlaid with the JSON file at ``path`` if it exists."""
    cfg: dict[str, Any] = json.loads(json.dumps(DEFAULTS))  # deep copy
    if path is None:
        return cfg
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config file not found: {p}")
    user = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(user, dict):
        raise ValueError(f"config file {p} must contain a JSON object")
    for key, value in user.items():
        if key not in cfg:
            raise ValueError(f"unknown config key: {key!r}")
        cfg[key] = value
    return cfg
