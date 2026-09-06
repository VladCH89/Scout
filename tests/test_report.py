import re

from scout.config import DEFAULTS
from scout.failures import FailureLog
from scout.models import TrendReading
from scout.report import build_payload, render_markdown
from scout.score import apply_ranking

from test_scoring import make, topic_with


def build():
    topic = topic_with([
        make("a", "r/AppIdeas", "2026-01-04"),
        make("b", "r/frugal", "2026-03-09"),
        make("c", "apple:123", "2026-04-01", source="apple_appstore"),
    ])
    topic.label = "grocery budget / shared budget"
    topic.main_keyword = "grocery budget"
    topic.trend = TrendReading("grocery budget", "rising", 33.0, 9.0, 12.0,
                               "today 12-m", "https://trends.google.com/trends/explore?q=x")
    failures = FailureLog()
    failures.record("google_trends", "invoice chasing", "interest_over_time", "HTTP 429")
    ranked, unranked = apply_ranking([topic], DEFAULTS)
    payload = build_payload(ranked, unranked, failures, DEFAULTS,
                            {"reddit_evidence_items": 2, "source_failures": 1})
    return payload


def test_every_evidence_item_carries_a_url():
    payload = build()
    for topic in payload["topics"] + payload["unranked_topics"]:
        assert topic["evidence"], "a topic must never appear without evidence"
        for item in topic["evidence"]:
            assert item["url"].startswith("http")
            assert item["quote"]


def test_markdown_links_every_quote_and_lists_failures():
    markdown = render_markdown(build())
    quotes = [line for line in markdown.splitlines() if line.startswith("> —")]
    assert quotes, "expected verbatim evidence lines"
    for line in quotes:
        assert re.search(r"\[source\]\(https?://", line)
    assert "## Source failures" in markdown
    assert "HTTP 429" in markdown
    assert "rising" in markdown


def test_empty_run_says_so_rather_than_inventing_topics():
    failures = FailureLog()
    failures.record("reddit", "r/AppIdeas", "search", "HTTP 403")
    payload = build_payload([], [], failures, DEFAULTS, {"source_failures": 1})
    markdown = render_markdown(payload)
    assert "No topic met the corroboration bar" in markdown
    assert "HTTP 403" in markdown
    assert payload["topics"] == []
