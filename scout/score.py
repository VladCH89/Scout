"""Scoring topics.

The shape of the score is fixed by the brief:

    base = log2(distinct_posts) × (1 + log2(distinct_communities))
                                × (1 + log2(distinct_months))

``log2(1) == 0``, so a topic supported by a single post scores exactly zero no
matter how loud that post is. The base is then adjusted by Google Trends
direction and by app-store complaint volume:

    score = base × (1 + trend_adjustment) × (1 + complaint_adjustment)

A topic ranks only if its evidence comes from at least ``min_independent_sources``
distinct origins (different subreddits, or a subreddit plus an app's reviews).
Google Trends never counts as corroboration — it is a directional reading of a
keyword, not an independent report of demand.
"""

from __future__ import annotations

import math

from .cluster import Topic
from .models import SOURCE_APPLE, SOURCE_GOOGLE_PLAY


def _complaint_adjustment(complaints: int, cfg: dict) -> float:
    if complaints <= 0:
        return 0.0
    weight = float(cfg["complaint_adjustment_weight"])
    cap = float(cfg["complaint_adjustment_cap"])
    return min(cap, weight * math.log10(1 + complaints))


def score_topic(topic: Topic, cfg: dict) -> None:
    """Compute and attach the score and its full breakdown to ``topic``."""
    distinct_posts = len({e.item_id for e in topic.evidence})
    distinct_communities = len(topic.origins)
    distinct_months = len(topic.months)

    posts_factor = math.log2(distinct_posts) if distinct_posts > 0 else 0.0
    communities_factor = 1 + math.log2(distinct_communities) if distinct_communities else 0.0
    months_factor = 1 + math.log2(distinct_months) if distinct_months else 1.0
    base = posts_factor * communities_factor * months_factor

    direction = topic.trend.direction if topic.trend else "unknown"
    trend_adj = float(cfg["trend_adjustment"].get(direction, 0.0))

    complaints = sum(
        1 for e in topic.evidence if e.source in (SOURCE_APPLE, SOURCE_GOOGLE_PLAY)
    )
    complaint_adj = _complaint_adjustment(complaints, cfg)

    score = base * (1 + trend_adj) * (1 + complaint_adj)

    topic.score = round(score, 3)
    topic.score_breakdown = {
        "distinct_posts": distinct_posts,
        "distinct_communities": distinct_communities,
        "distinct_months": distinct_months,
        "posts_factor": round(posts_factor, 3),
        "communities_factor": round(communities_factor, 3),
        "months_factor": round(months_factor, 3),
        "base": round(base, 3),
        "trend_direction": direction,
        "trend_adjustment": trend_adj,
        "appstore_complaints": complaints,
        "complaint_adjustment": round(complaint_adj, 3),
        "formula": "log2(posts) * (1+log2(communities)) * (1+log2(months)) "
                   "* (1+trend_adjustment) * (1+complaint_adjustment)",
    }


def apply_ranking(topics: list[Topic], cfg: dict) -> tuple[list[Topic], list[Topic]]:
    """Score every topic and split it into ranked and unranked lists."""
    minimum = int(cfg["min_independent_sources"])
    ranked: list[Topic] = []
    unranked: list[Topic] = []

    for topic in topics:
        score_topic(topic, cfg)
        independent = len(topic.origins)
        if independent < minimum:
            topic.ranked = False
            topic.unranked_reason = (
                f"only {independent} independent source(s) "
                f"({', '.join(topic.origins) or 'none'}); {minimum} required"
            )
            unranked.append(topic)
        elif topic.score <= 0:
            topic.ranked = False
            topic.unranked_reason = (
                "score is zero: a single distinct post cannot establish demand"
            )
            unranked.append(topic)
        else:
            topic.ranked = True
            ranked.append(topic)

    ranked.sort(key=lambda t: (-t.score, t.topic_id))
    unranked.sort(key=lambda t: (-t.score, t.topic_id))
    return ranked, unranked
