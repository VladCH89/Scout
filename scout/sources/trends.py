"""Google Trends via pytrends: 12-month search-interest direction.

Trends is an *adjustment*, never corroboration. When it fails — pytrends is
unauthenticated and rate-limits aggressively — the direction stays ``unknown``,
the adjustment is zero, and the failure is recorded.
"""

from __future__ import annotations

import logging
import time
from urllib.parse import quote_plus

from ..cluster import Topic
from ..failures import FailureLog
from ..models import TrendReading

log = logging.getLogger("scout")

SOURCE = "google_trends"


def explore_url(keyword: str, timeframe: str, geo: str) -> str:
    url = f"https://trends.google.com/trends/explore?date={quote_plus(timeframe)}&q={quote_plus(keyword)}"
    if geo:
        url += f"&geo={quote_plus(geo)}"
    return url


def _direction(first: float, last: float, threshold_pct: float) -> tuple[str, float | None]:
    if first <= 0:
        if last > 0:
            return "rising", None
        return "flat", 0.0
    change = (last - first) / first * 100.0
    if change >= threshold_pct:
        return "rising", change
    if change <= -threshold_pct:
        return "falling", change
    return "flat", change


def annotate(topics: list[Topic], cfg: dict, failures: FailureLog) -> None:
    """Attach a TrendReading to each of the top ``trends_max_topics`` topics."""
    timeframe = cfg["trends_timeframe"]
    geo = cfg["trends_geo"]
    threshold = float(cfg["trends_direction_threshold_pct"])

    if not cfg["trends_enabled"]:
        for topic in topics:
            topic.trend = TrendReading(
                keyword=topic.main_keyword, direction="unknown", change_pct=None,
                first_window_mean=None, last_window_mean=None, timeframe=timeframe,
                url=explore_url(topic.main_keyword, timeframe, geo),
                note="Google Trends disabled by configuration; no adjustment applied",
            )
        failures.record(SOURCE, "all topics", "config", "trends_enabled is false")
        return

    try:
        from pytrends.request import TrendReq
    except Exception as exc:  # pragma: no cover - import environment issue
        failures.record(SOURCE, "all topics", "import", f"pytrends unavailable: {exc}")
        for topic in topics:
            topic.trend = TrendReading(
                keyword=topic.main_keyword, direction="unknown", change_pct=None,
                first_window_mean=None, last_window_mean=None, timeframe=timeframe,
                url=explore_url(topic.main_keyword, timeframe, geo),
                note=f"pytrends unavailable: {exc}",
            )
        return

    try:
        client = TrendReq(hl="en-US", tz=0)
    except Exception as exc:
        failures.record(SOURCE, "all topics", "client", f"could not start pytrends: {exc}")
        return

    budget = int(cfg["trends_max_topics"])
    delay = float(cfg["trends_request_delay_seconds"])

    for index, topic in enumerate(topics):
        keyword = topic.main_keyword
        url = explore_url(keyword, timeframe, geo)
        if not keyword:
            failures.record(SOURCE, topic.topic_id, "keyword", "topic has no main keyword")
            topic.trend = TrendReading(keyword="", direction="unknown", change_pct=None,
                                       first_window_mean=None, last_window_mean=None,
                                       timeframe=timeframe, url=url,
                                       note="no keyword could be derived from the cluster")
            continue
        if index >= budget:
            topic.trend = TrendReading(
                keyword=keyword, direction="unknown", change_pct=None,
                first_window_mean=None, last_window_mean=None, timeframe=timeframe, url=url,
                note=f"not queried: outside the trends_max_topics budget of {budget}",
            )
            continue

        try:
            client.build_payload([keyword], timeframe=timeframe, geo=geo)
            frame = client.interest_over_time()
        except Exception as exc:
            failures.record(SOURCE, keyword, "interest_over_time", f"{type(exc).__name__}: {exc}")
            topic.trend = TrendReading(
                keyword=keyword, direction="unknown", change_pct=None,
                first_window_mean=None, last_window_mean=None, timeframe=timeframe, url=url,
                note=f"query failed: {type(exc).__name__}: {exc}",
            )
            time.sleep(delay)
            continue

        if frame is None or getattr(frame, "empty", True) or keyword not in frame:
            failures.record(SOURCE, keyword, "interest_over_time", "no data returned for keyword")
            topic.trend = TrendReading(
                keyword=keyword, direction="unknown", change_pct=None,
                first_window_mean=None, last_window_mean=None, timeframe=timeframe, url=url,
                note="Google Trends returned no series for this keyword",
            )
            time.sleep(delay)
            continue

        series = frame[keyword]
        if "isPartial" in frame:
            series = series[~frame["isPartial"].astype(bool)]
        values = [float(v) for v in series.tolist()]
        if len(values) < 8:
            failures.record(SOURCE, keyword, "interest_over_time",
                            f"series too short to read a direction ({len(values)} points)")
            topic.trend = TrendReading(
                keyword=keyword, direction="unknown", change_pct=None,
                first_window_mean=None, last_window_mean=None, timeframe=timeframe, url=url,
                note=f"series too short ({len(values)} points)",
            )
            time.sleep(delay)
            continue

        window = max(4, len(values) // 4)
        first_mean = sum(values[:window]) / window
        last_mean = sum(values[-window:]) / window
        direction, change = _direction(first_mean, last_mean, threshold)
        topic.trend = TrendReading(
            keyword=keyword,
            direction=direction,
            change_pct=round(change, 1) if change is not None else None,
            first_window_mean=round(first_mean, 2),
            last_window_mean=round(last_mean, 2),
            timeframe=timeframe,
            url=url,
            note=f"mean of first {window} vs last {window} points of the {timeframe} series",
        )
        log.info("trends %-28s %-7s (%s)", keyword, direction,
                 f"{change:+.1f}%" if change is not None else "baseline was zero")
        time.sleep(delay)
