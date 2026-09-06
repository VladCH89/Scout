"""Data structures shared across the scout.

Every piece of evidence carries the raw values only: a verbatim quote, the
source it came from, a resolvable URL, a date and a score/rating. Nothing in
this module ever derives, paraphrases or estimates content.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# Source identifiers. Only primary data sources are permitted; secondary
# commentary (blogs, listicles, "top app ideas" articles) is never collected.
SOURCE_REDDIT = "reddit"
SOURCE_APPLE = "apple_appstore"
SOURCE_GOOGLE_PLAY = "google_play"

EVIDENCE_SOURCES = (SOURCE_REDDIT, SOURCE_APPLE, SOURCE_GOOGLE_PLAY)


@dataclass
class Evidence:
    """A single verbatim demand signal.

    Attributes:
        source: one of EVIDENCE_SOURCES.
        origin: the independent channel it came from, e.g. ``r/AppIdeas``,
            ``apple:1234567890`` or ``play:com.example.app``. Two evidence
            items corroborate each other only if their origins differ.
        quote: the exact sentence (or review line) containing the matched
            signal, copied verbatim from the source payload.
        full_text: the complete raw text of the item, verbatim.
        url: permalink to the item, or to the item's parent listing when the
            source exposes no per-item permalink (app store reviews).
        date: ISO ``YYYY-MM-DD`` as reported by the source.
        score: upvotes (reddit) or star rating (app stores).
        score_kind: ``upvotes`` or ``stars``.
        matched_phrase: which configured demand phrase / complaint pattern hit.
    """

    source: str
    origin: str
    quote: str
    full_text: str
    url: str
    date: str
    score: float | None
    score_kind: str
    matched_phrase: str
    item_id: str
    title: str = ""
    author: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def month(self) -> str:
        return self.date[:7] if len(self.date) >= 7 else ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["month"] = self.month
        return d


@dataclass
class Failure:
    """An explicitly recorded source failure.

    A failure is never papered over with a guess or an estimate: it is stored
    in the output so the gap is visible in the record.
    """

    source: str
    target: str
    stage: str
    error: str
    at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrendReading:
    """A Google Trends 12-month reading for a topic's main keyword."""

    keyword: str
    direction: str  # rising | flat | falling | unknown
    change_pct: float | None
    first_window_mean: float | None
    last_window_mean: float | None
    timeframe: str
    url: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
