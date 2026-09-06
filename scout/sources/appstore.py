"""App store reviews: Apple RSS + Google Play.

For each topic the scout searches both stores for apps matching the topic's
main keyword, pulls 1- and 2-star reviews, and keeps only the reviews that
literally complain about a missing feature. Quotes are copied verbatim; the
stored URL is the deep link to the review (or, when a store exposes none, the
app's review listing), and the feed the review came from is stored alongside it
so every claim can be traced back to the exact payload.
"""

from __future__ import annotations

import logging
import time

from ..cluster import Topic
from ..failures import FailureLog
from ..http import HttpError, get_json
from ..models import SOURCE_APPLE, SOURCE_GOOGLE_PLAY, Evidence
from ..text import extract_quote, find_phrase

log = logging.getLogger("scout")

ITUNES_SEARCH = "https://itunes.apple.com/search"
ITUNES_REVIEWS = (
    "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/"
    "sortBy=mostRecent/page={page}/json"
)
REVIEWS_PER_APPLE_PAGE = 50


# --------------------------------------------------------------------------
# Apple
# --------------------------------------------------------------------------
def _apple_search(keyword: str, cfg: dict, failures: FailureLog) -> list[dict]:
    try:
        payload = get_json(
            ITUNES_SEARCH,
            user_agent=cfg["reddit_user_agent"],
            params={
                "term": keyword,
                "country": cfg["appstore_country"],
                "entity": "software",
                "limit": int(cfg["appstore_apps_per_topic"]),
            },
        )
    except HttpError as exc:
        failures.record(SOURCE_APPLE, f"search {keyword!r}", "search", str(exc))
        return []
    results = (payload or {}).get("results") or []
    if not results:
        failures.record(SOURCE_APPLE, f"search {keyword!r}", "search", "no apps matched the keyword")
    return results


def _apple_reviews(app_id: str, cfg: dict, failures: FailureLog) -> list[dict]:
    country = cfg["appstore_country"]
    wanted = int(cfg["appstore_reviews_per_app"])
    pages = max(1, min(10, -(-wanted // REVIEWS_PER_APPLE_PAGE)))
    entries: list[dict] = []
    for page in range(1, pages + 1):
        url = ITUNES_REVIEWS.format(country=country, app_id=app_id, page=page)
        try:
            payload = get_json(url, user_agent=cfg["reddit_user_agent"])
        except HttpError as exc:
            failures.record(SOURCE_APPLE, f"app {app_id} page {page}", "reviews", str(exc))
            break
        page_entries = ((payload or {}).get("feed") or {}).get("entry") or []
        if isinstance(page_entries, dict):  # single-entry feeds are not wrapped
            page_entries = [page_entries]
        # The first entry of page 1 describes the app itself, not a review.
        page_entries = [e for e in page_entries if "im:rating" in e]
        if not page_entries:
            if page == 1:
                failures.record(SOURCE_APPLE, f"app {app_id}", "reviews",
                                "review feed returned no review entries")
            break
        for entry in page_entries:
            entry["_feed_url"] = url
        entries.extend(page_entries)
        time.sleep(float(cfg["appstore_request_delay_seconds"]))
    return entries[:wanted]


def _apple_evidence(app: dict, entries: list[dict], cfg: dict) -> list[Evidence]:
    app_id = str(app.get("trackId") or "")
    app_name = app.get("trackName") or ""
    listing_url = app.get("trackViewUrl") or (
        f"https://apps.apple.com/{cfg['appstore_country']}/app/id{app_id}?see-all=reviews"
    )
    max_rating = int(cfg["appstore_max_rating"])
    patterns: list[str] = cfg["missing_feature_patterns"]

    out: list[Evidence] = []
    for entry in entries:
        try:
            rating = int(((entry.get("im:rating") or {}).get("label") or "0"))
        except (TypeError, ValueError):
            continue
        if rating > max_rating or rating < 1:
            continue
        title = ((entry.get("title") or {}).get("label") or "").strip()
        content = ((entry.get("content") or {}).get("label") or "").strip()
        combined = f"{title}\n{content}".strip()
        matched = find_phrase(combined, patterns)
        if matched is None:
            continue
        review_id = ((entry.get("id") or {}).get("label") or "").strip()
        href = ((entry.get("link") or {}).get("attributes") or {}).get("href") or ""
        updated = ((entry.get("updated") or {}).get("label") or "")[:10]
        out.append(
            Evidence(
                source=SOURCE_APPLE,
                origin=f"apple:{app_id}",
                quote=extract_quote(combined, matched),
                full_text=combined,
                url=href or listing_url,
                date=updated,
                score=float(rating),
                score_kind="stars",
                matched_phrase=matched,
                item_id=f"apple:{app_id}:{review_id or str(abs(hash(combined)))}",
                title=title,
                author=(((entry.get("author") or {}).get("name") or {}).get("label") or ""),
                extra={
                    "app_name": app_name,
                    "app_id": app_id,
                    "app_listing_url": listing_url,
                    "feed_url": entry.get("_feed_url", ""),
                    "review_permalink_available": bool(href),
                    "app_version": ((entry.get("im:version") or {}).get("label") or ""),
                },
            )
        )
    return out


# --------------------------------------------------------------------------
# Google Play
# --------------------------------------------------------------------------
def _play_evidence(keyword: str, cfg: dict, failures: FailureLog) -> list[Evidence]:
    try:
        from google_play_scraper import Sort, reviews as gp_reviews, search as gp_search
    except Exception as exc:  # pragma: no cover - import environment issue
        failures.record(SOURCE_GOOGLE_PLAY, f"search {keyword!r}", "import",
                        f"google-play-scraper unavailable: {exc}")
        return []

    country = cfg["appstore_country"]
    patterns: list[str] = cfg["missing_feature_patterns"]
    out: list[Evidence] = []

    try:
        apps = gp_search(keyword, lang="en", country=country,
                         n_hits=int(cfg["appstore_apps_per_topic"]))
    except Exception as exc:
        failures.record(SOURCE_GOOGLE_PLAY, f"search {keyword!r}", "search",
                        f"{type(exc).__name__}: {exc}")
        return []
    if not apps:
        failures.record(SOURCE_GOOGLE_PLAY, f"search {keyword!r}", "search",
                        "no apps matched the keyword")
        return []

    for app in apps:
        app_id = app.get("appId") or ""
        if not app_id:
            continue
        app_name = app.get("title") or ""
        listing_url = f"https://play.google.com/store/apps/details?id={app_id}"
        collected: list[dict] = []
        for star in range(1, int(cfg["appstore_max_rating"]) + 1):
            try:
                batch, _token = gp_reviews(
                    app_id,
                    lang="en",
                    country=country,
                    sort=Sort.NEWEST,
                    count=int(cfg["appstore_reviews_per_app"]),
                    filter_score_with=star,
                )
            except Exception as exc:
                failures.record(SOURCE_GOOGLE_PLAY, f"{app_id} ({star}-star)", "reviews",
                                f"{type(exc).__name__}: {exc}")
                continue
            collected.extend(batch or [])
            time.sleep(float(cfg["appstore_request_delay_seconds"]))

        if not collected:
            failures.record(SOURCE_GOOGLE_PLAY, app_id, "reviews",
                            "no 1- or 2-star reviews returned")
            continue

        for review in collected:
            content = (review.get("content") or "").strip()
            if not content:
                continue
            matched = find_phrase(content, patterns)
            if matched is None:
                continue
            review_id = review.get("reviewId") or ""
            at = review.get("at")
            date = at.strftime("%Y-%m-%d") if hasattr(at, "strftime") else str(at or "")[:10]
            out.append(
                Evidence(
                    source=SOURCE_GOOGLE_PLAY,
                    origin=f"play:{app_id}",
                    quote=extract_quote(content, matched),
                    full_text=content,
                    url=f"{listing_url}&reviewId={review_id}" if review_id else listing_url,
                    date=date,
                    score=float(review.get("score") or 0),
                    score_kind="stars",
                    matched_phrase=matched,
                    item_id=f"play:{app_id}:{review_id or str(abs(hash(content)))}",
                    title="",
                    author=review.get("userName") or "",
                    extra={
                        "app_name": app_name,
                        "app_id": app_id,
                        "app_listing_url": listing_url,
                        "thumbs_up": review.get("thumbsUpCount"),
                        "app_version": review.get("reviewCreatedVersion") or "",
                    },
                )
            )
    return out


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------
def annotate(topics: list[Topic], cfg: dict, failures: FailureLog) -> int:
    """Attach app-store complaint evidence to the top topics. Returns the count."""
    if not cfg["appstore_enabled"]:
        failures.record("app_stores", "all topics", "config", "appstore_enabled is false")
        return 0

    budget = int(cfg["appstore_max_topics"])
    added = 0
    for topic in topics[:budget]:
        keyword = topic.main_keyword
        if not keyword:
            failures.record("app_stores", topic.topic_id, "keyword", "topic has no main keyword")
            continue

        found: list[Evidence] = []
        for app in _apple_search(keyword, cfg, failures):
            app_id = str(app.get("trackId") or "")
            if not app_id:
                continue
            entries = _apple_reviews(app_id, cfg, failures)
            found.extend(_apple_evidence(app, entries, cfg))
        found.extend(_play_evidence(keyword, cfg, failures))

        known = {e.item_id for e in topic.evidence}
        for item in found:
            if item.item_id in known:
                continue
            known.add(item.item_id)
            topic.evidence.append(item)
            added += 1
        log.info("app stores %-28s %d missing-feature complaints", keyword, len(found))
        if not found:
            failures.record("app_stores", keyword, "match",
                            "no 1-2 star review mentioned a missing feature")
    return added
