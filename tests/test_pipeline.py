"""End-to-end pipeline test against fixture payloads.

The sandbox this was developed in blocks the live hosts, so the collectors are
exercised against payloads shaped exactly like the real ones: a Reddit
``search.json`` listing and an iTunes ``customerreviews`` feed.
"""

import json

import pytest

from scout import report
from scout.cluster import cluster
from scout.config import DEFAULTS
from scout.failures import FailureLog
from scout.score import apply_ranking
from scout.sources import appstore, reddit

CFG = dict(DEFAULTS, subreddits=["AppIdeas", "frugal"], reddit_request_delay_seconds=0,
           appstore_request_delay_seconds=0, appstore_apps_per_topic=1,
           appstore_reviews_per_app=50, appstore_max_topics=3)

POSTS = {
    "AppIdeas": [
        ("a1", "I wish there was an app to split recurring grocery bills with roommates",
         "We keep doing this in a spreadsheet and it breaks every month.", 1767225600, 84),
        ("a2", "Why is there no simple shared grocery budget tracker?",
         "Every app I try is a full budgeting suite.", 1772496000, 51),
    ],
    "frugal": [
        ("f1", "Is there an app that splits grocery bills between housemates?",
         "Splitwise does not do recurring grocery runs well.", 1777680000, 33),
        ("f2", "Completely unrelated post about coupon binders", "", 1777680000, 9),
    ],
}


def reddit_payload(subreddit, phrase):
    children = []
    for post_id, title, body, created, score in POSTS[subreddit]:
        children.append({"kind": "t3", "data": {
            "id": post_id, "title": title, "selftext": body, "subreddit": subreddit,
            "permalink": f"/r/{subreddit}/comments/{post_id}/x/", "score": score,
            "created_utc": created, "num_comments": 7, "author": "redditor",
            "upvote_ratio": 0.93}})
    return {"kind": "Listing", "data": {"children": children}}


ITUNES_SEARCH = {"resultCount": 1, "results": [
    {"trackId": 555000111, "trackName": "SplitBudget",
     "trackViewUrl": "https://apps.apple.com/us/app/splitbudget/id555000111"}]}

ITUNES_REVIEWS = {"feed": {"entry": [
    {"im:rating": {"label": "1"}, "id": {"label": "1001"},
     "title": {"label": "No way to split a recurring grocery bill"},
     "content": {"label": "There is no way to split a recurring grocery bill between two people."},
     "link": {"attributes": {"href": "https://itunes.apple.com/us/review?id=555000111&type=Purple%20Software"}},
     "updated": {"label": "2026-05-02T09:11:00-07:00"},
     "author": {"name": {"label": "reviewer"}}, "im:version": {"label": "4.1"}},
    {"im:rating": {"label": "1"}, "id": {"label": "1002"},
     "title": {"label": "Fine otherwise"},
     "content": {"label": "Crashes on launch sometimes."},
     "link": {"attributes": {"href": "https://itunes.apple.com/us/review?id=2"}},
     "updated": {"label": "2026-05-03T09:11:00-07:00"},
     "author": {"name": {"label": "other"}}, "im:version": {"label": "4.1"}},
    {"im:rating": {"label": "5"}, "id": {"label": "1003"},
     "title": {"label": "Love it"}, "content": {"label": "No way to fault it."},
     "link": {"attributes": {"href": "https://itunes.apple.com/us/review?id=3"}},
     "updated": {"label": "2026-05-04T09:11:00-07:00"},
     "author": {"name": {"label": "fan"}}, "im:version": {"label": "4.1"}},
]}}


@pytest.fixture
def wired(monkeypatch):
    def fake_reddit_get(url, **kwargs):
        subreddit = url.split("/r/")[1].split("/")[0]
        return reddit_payload(subreddit, kwargs["params"]["q"])

    def fake_itunes_get(url, **kwargs):
        if "/search" in url:
            return ITUNES_SEARCH
        if "page=1" in url:
            return ITUNES_REVIEWS
        return {"feed": {"entry": []}}

    monkeypatch.setattr(reddit, "get_json", fake_reddit_get)
    monkeypatch.setattr(appstore, "get_json", fake_itunes_get)
    # Google Play and Trends are exercised through their failure paths.
    monkeypatch.setattr(appstore, "_play_evidence", lambda kw, cfg, f: [])


def test_reddit_collect_keeps_only_verified_phrase_matches(wired):
    failures = FailureLog()
    evidence = reddit.collect(CFG, failures)
    ids = {e.item_id for e in evidence}
    assert ids == {"reddit:a1", "reddit:a2", "reddit:f1"}  # f2 matches no phrase
    item = next(e for e in evidence if e.item_id == "reddit:a1")
    assert item.url == "https://www.reddit.com/r/AppIdeas/comments/a1/x/"
    assert item.date == "2026-01-01"
    assert item.score == 84
    assert item.quote in f"{item.title}\n{item.full_text.split(chr(10), 1)[-1]}"
    assert item.matched_phrase == "wish there was"


def test_apple_reviews_keep_only_low_star_missing_feature_complaints(wired):
    failures = FailureLog()
    one_topic = dict(CFG, appstore_max_topics=1)
    topics = cluster(reddit.collect(CFG, failures), CFG["cluster_similarity_threshold"])
    added = appstore.annotate(topics, one_topic, failures)
    apple = [e for t in topics for e in t.evidence if e.source == "apple_appstore"]
    assert added == len(apple) == 1
    complaint = apple[0]
    assert complaint.score == 1.0  # the 5-star "no way to fault it" is excluded
    assert complaint.matched_phrase == "no way to"
    assert complaint.url.startswith("https://itunes.apple.com/us/review?id=555000111")
    assert complaint.extra["feed_url"].startswith("https://itunes.apple.com/us/rss/customerreviews/")


def test_full_run_ranks_the_corroborated_topic_and_records_failures(wired, tmp_path):
    failures = FailureLog()
    topics = cluster(reddit.collect(CFG, failures), CFG["cluster_similarity_threshold"])
    appstore.annotate(topics, CFG, failures)
    ranked, unranked = apply_ranking(topics, CFG)

    assert ranked, "the grocery-splitting topic is backed by two subreddits"
    top = ranked[0]
    assert len(top.origins) >= 2
    assert top.score > 0

    payload = report.build_payload(ranked, unranked, failures, CFG,
                                   {"topics_ranked": len(ranked), "source_failures": len(failures)})
    json_path = report.write_json(payload, tmp_path)
    md_path = report.write_markdown(payload, tmp_path)

    stored = json.loads(json_path.read_text())
    assert stored["run_date"] == payload["run_date"]
    for topic in stored["topics"]:
        for item in topic["evidence"]:
            assert item["url"].startswith("http")

    markdown = md_path.read_text()
    assert "https://www.reddit.com/r/AppIdeas/comments/a1/x/" in markdown
    assert "## Source failures" in markdown
    # Google Trends was never reached in this run, so no direction is claimed.
    assert all(t["trend"] is None or t["trend"]["direction"] == "unknown"
               for t in stored["topics"])


def test_cli_run_writes_both_files(wired, tmp_path, monkeypatch):
    """The CLI wiring itself: collect → cluster → enrich → score → write."""
    from scout import main as main_module

    monkeypatch.setattr(main_module, "load_config", lambda path: dict(CFG))
    args = main_module.parse_args([
        "--config", "does-not-exist.json", "--out-dir", str(tmp_path),
        "--skip-trends", "--skip-appstore",
    ])
    assert main_module.run(args) == 0

    written = sorted(p.name for p in tmp_path.iterdir())
    assert "latest.md" in written
    assert any(name.endswith(".json") for name in written)

    payload = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert payload["stats"]["reddit_evidence_items"] == 3
    assert payload["stats"]["topics_ranked"] == len(payload["topics"])
    # Both skips are recorded as explicit failures rather than passing silently.
    sources = {f["source"] for f in payload["failures"]}
    assert {"google_trends", "app_stores"} <= sources
