"""Reddit public JSON API (the ``.json`` endpoints, no auth).

For each configured subreddit the scout runs one search per demand phrase and
keeps only posts where the phrase is actually present in the title or body —
Reddit's search is fuzzy, and an unverified hit would be an unsupported claim.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from ..failures import FailureLog
from ..http import HttpError, get_json
from ..models import SOURCE_REDDIT, Evidence
from ..text import extract_quote, find_phrase

log = logging.getLogger("scout")

SEARCH_URL = "https://www.reddit.com/r/{subreddit}/search.json"


def _iso_date(created_utc: float | None) -> str:
    if not created_utc:
        return ""
    return datetime.fromtimestamp(float(created_utc), tz=timezone.utc).strftime("%Y-%m-%d")


def collect(cfg: dict, failures: FailureLog) -> list[Evidence]:
    """Return verbatim demand-signal posts from the configured subreddits."""
    phrases: list[str] = cfg["demand_phrases"]
    user_agent: str = cfg["reddit_user_agent"]
    delay: float = float(cfg["reddit_request_delay_seconds"])

    seen: set[str] = set()
    evidence: list[Evidence] = []

    for subreddit in cfg["subreddits"]:
        hits_for_sub = 0
        for phrase in phrases:
            target = f"r/{subreddit} :: {phrase!r}"
            params = {
                "q": f'"{phrase}"',
                "restrict_sr": "on",
                "sort": "new",
                "t": cfg["reddit_timeframe"],
                "limit": int(cfg["reddit_limit_per_query"]),
                "include_over_18": "on",
            }
            try:
                payload = get_json(
                    SEARCH_URL.format(subreddit=subreddit),
                    user_agent=user_agent,
                    params=params,
                )
            except HttpError as exc:
                failures.record(SOURCE_REDDIT, target, "search", str(exc))
                time.sleep(delay)
                continue

            children = (payload or {}).get("data", {}).get("children", [])
            if not children:
                failures.record(
                    SOURCE_REDDIT, target, "search", "search returned zero posts"
                )
                time.sleep(delay)
                continue

            for child in children:
                post = child.get("data") or {}
                post_id = post.get("id") or ""
                if not post_id or post_id in seen:
                    continue
                title = post.get("title") or ""
                body = post.get("selftext") or ""
                combined = f"{title}\n{body}".strip()
                # Verify the phrase really occurs; Reddit search is fuzzy.
                matched = find_phrase(combined, [phrase])
                if matched is None:
                    continue
                permalink = post.get("permalink") or ""
                url = f"https://www.reddit.com{permalink}" if permalink else (post.get("url") or "")
                if not url:
                    failures.record(
                        SOURCE_REDDIT, f"r/{subreddit} post {post_id}", "parse",
                        "post has no permalink; dropped because it cannot be traced to a URL",
                    )
                    continue
                seen.add(post_id)
                hits_for_sub += 1
                evidence.append(
                    Evidence(
                        source=SOURCE_REDDIT,
                        origin=f"r/{post.get('subreddit') or subreddit}",
                        quote=extract_quote(combined, matched),
                        full_text=combined,
                        url=url,
                        date=_iso_date(post.get("created_utc")),
                        score=post.get("score"),
                        score_kind="upvotes",
                        matched_phrase=matched,
                        item_id=f"reddit:{post_id}",
                        title=title,
                        author=post.get("author") or "",
                        extra={
                            "num_comments": post.get("num_comments"),
                            "upvote_ratio": post.get("upvote_ratio"),
                            "subreddit": post.get("subreddit") or subreddit,
                            "flair": post.get("link_flair_text") or "",
                        },
                    )
                )
            time.sleep(delay)

        log.info("reddit r/%s: %d verified posts", subreddit, hits_for_sub)
        if hits_for_sub == 0:
            failures.record(
                SOURCE_REDDIT, f"r/{subreddit}", "collect",
                "no posts matched any demand phrase after verification",
            )

    return evidence
