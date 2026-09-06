"""Clustering candidates into topics.

Deliberately simple and deterministic: IDF-weighted keyword bags plus greedy
agglomeration. No model, no network, no hidden state — the same evidence always
produces the same topics, which matters because the topics are what the report
makes claims about.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .models import Evidence, TrendReading
from .text import idf_weights, keyword_bag, merge_surfaces, similarity, surface_for


@dataclass
class Topic:
    topic_id: str
    evidence: list[Evidence] = field(default_factory=list)
    centroid: Counter = field(default_factory=Counter)
    surfaces: dict = field(default_factory=dict)
    label: str = ""
    keywords: list[str] = field(default_factory=list)
    main_keyword: str = ""
    trend: TrendReading | None = None
    score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)
    ranked: bool = False
    unranked_reason: str = ""

    def add(self, item: Evidence, counts: Counter,
            surfaces: dict[str, Counter] | None = None) -> None:
        self.evidence.append(item)
        self.centroid.update(counts)
        if surfaces:
            merge_surfaces(self.surfaces, surfaces)

    @property
    def origins(self) -> list[str]:
        return sorted({e.origin for e in self.evidence})

    @property
    def months(self) -> list[str]:
        return sorted({e.month for e in self.evidence if e.month})

    def counts_by_source(self) -> dict[str, int]:
        out: Counter[str] = Counter(e.source for e in self.evidence)
        return dict(sorted(out.items()))


def _sort_key(item: Evidence) -> tuple:
    # Newest first, then a stable tiebreaker, so runs are reproducible.
    return (item.date or "", item.item_id)


# Bigrams are down-weighted for *matching* (see text.BIGRAM_WEIGHT) but they are
# what makes a label and a search keyword specific, so they are boosted back up
# for *naming*.
LABEL_BIGRAM_BOOST = 2.5


def label_for(
    centroid: Counter,
    idf: dict[str, float],
    surfaces: dict[str, Counter] | None = None,
    size: int = 4,
) -> tuple[str, list[str], str]:
    """Return ``(label, keywords, main_keyword)`` for a centroid.

    Keywords are rendered in the spellings the sources actually used, so the
    Google Trends query and the app-store search are real words.
    """
    surfaces = surfaces or {}

    def weight(term: str, count: float) -> float:
        boost = LABEL_BIGRAM_BOOST if " " in term else 1.0
        return count * idf.get(term, 1.0) * boost

    ranked = sorted(centroid.items(), key=lambda kv: (weight(*kv), kv[0]), reverse=True)
    keywords = [surface_for(term, surfaces) for term, _ in ranked[:size]]
    main_term = next((term for term, _ in ranked if " " in term), None)
    if main_term is None:
        main_term = ranked[0][0] if ranked else ""
    main = surface_for(main_term, surfaces) if main_term else ""
    label = " / ".join(keywords[:3]) if keywords else "(unlabelled)"
    return label, keywords, main


def cluster(evidence: list[Evidence], threshold: float) -> list[Topic]:
    """Group evidence into topics by IDF-weighted keyword similarity."""
    items = sorted(evidence, key=_sort_key, reverse=True)
    if not items:
        return []

    pairs = [keyword_bag(f"{e.title}\n{e.quote}" if e.title else e.quote) for e in items]
    bags = [bag for bag, _ in pairs]
    idf = idf_weights(bags)

    topics: list[Topic] = []
    for item, (bag, surfaces) in zip(items, pairs):
        best: Topic | None = None
        best_sim = 0.0
        for topic in topics:
            sim = similarity(bag, topic.centroid, idf)
            if sim > best_sim:
                best_sim, best = sim, topic
        if best is not None and best_sim >= threshold:
            best.add(item, bag, surfaces)
        else:
            topic = Topic(topic_id=f"t{len(topics) + 1:03d}")
            topic.add(item, bag, surfaces)
            topics.append(topic)

    for topic in topics:
        topic.label, topic.keywords, topic.main_keyword = label_for(
            topic.centroid, idf, topic.surfaces
        )
    return topics
