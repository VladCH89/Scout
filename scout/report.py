"""Report rendering: dated JSON plus a readable ``latest.md``.

Every claim in both files is either a stored verbatim quote with its URL, or a
number computed from those stored items. Nothing is summarised into prose that
cannot be traced back to a link.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .cluster import Topic
from .failures import FailureLog
from .models import SOURCE_APPLE, SOURCE_GOOGLE_PLAY, SOURCE_REDDIT

SOURCE_LABELS = {
    SOURCE_REDDIT: "Reddit",
    SOURCE_APPLE: "Apple App Store",
    SOURCE_GOOGLE_PLAY: "Google Play",
}


def _topic_dict(topic: Topic, rank: int | None) -> dict:
    return {
        "rank": rank,
        "topic_id": topic.topic_id,
        "label": topic.label,
        "keywords": topic.keywords,
        "main_keyword": topic.main_keyword,
        "score": topic.score,
        "score_breakdown": topic.score_breakdown,
        "ranked": topic.ranked,
        "unranked_reason": topic.unranked_reason,
        "independent_sources": topic.origins,
        "months": topic.months,
        "evidence_counts": {
            **{key: topic.counts_by_source().get(key, 0) for key in SOURCE_LABELS},
            "total": len(topic.evidence),
        },
        "trend": topic.trend.to_dict() if topic.trend else None,
        "evidence": [e.to_dict() for e in sorted(topic.evidence, key=lambda e: e.date, reverse=True)],
    }


def build_payload(
    ranked: list[Topic],
    unranked: list[Topic],
    failures: FailureLog,
    cfg: dict,
    stats: dict,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "run_date": now.strftime("%Y-%m-%d"),
        "rules": [
            "Every claim traces to a stored source URL.",
            "Quotes are verbatim; nothing is paraphrased or invented.",
            "Source failures are recorded, never filled with an estimate.",
            "Primary data only: no blogs, listicles or 'top app ideas' commentary.",
            f"A topic ranks only with corroboration from at least "
            f"{cfg['min_independent_sources']} independent sources.",
        ],
        "config": {
            "subreddits": cfg["subreddits"],
            "demand_phrases": cfg["demand_phrases"],
            "reddit_timeframe": cfg["reddit_timeframe"],
            "trends_timeframe": cfg["trends_timeframe"],
            "appstore_country": cfg["appstore_country"],
            "appstore_max_rating": cfg["appstore_max_rating"],
            "min_independent_sources": cfg["min_independent_sources"],
            "cluster_similarity_threshold": cfg["cluster_similarity_threshold"],
        },
        "stats": stats,
        "failures": failures.to_list(),
        "topics": [_topic_dict(t, i + 1) for i, t in enumerate(ranked)],
        "unranked_topics": [_topic_dict(t, None) for t in unranked],
    }


def write_json(payload: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{payload['run_date']}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _one_line(text: str, limit: int = 300) -> str:
    flat = " ".join(text.split())
    if len(flat) > limit:
        flat = flat[:limit].rstrip() + " …[truncated]"
    return flat


def _evidence_line(item: dict) -> str:
    score = item.get("score")
    if item.get("score_kind") == "stars" and score is not None:
        meta = f"{int(score)}★"
    elif score is not None:
        meta = f"{int(score)} upvotes"
    else:
        meta = "score unavailable"
    app = (item.get("extra") or {}).get("app_name")
    origin = f"{item['origin']}" + (f" ({app})" if app else "")
    date = item.get("date") or "date unavailable"
    return (
        f"> {_one_line(item['quote'])}\n>\n"
        f"> — {origin}, {date}, {meta}, matched “{item['matched_phrase']}” "
        f"· [source]({item['url']})"
    )


def _trend_line(trend: dict | None) -> str:
    if not trend:
        return "**Trend (12 mo):** not read — no reading stored."
    change = trend.get("change_pct")
    change_text = f" ({change:+.1f}%)" if isinstance(change, (int, float)) else ""
    note = f" — {trend['note']}" if trend.get("note") else ""
    keyword = trend.get("keyword") or "(no keyword)"
    return (
        f"**Trend (12 mo):** `{keyword}` → **{trend['direction']}**{change_text}{note} "
        f"· [Google Trends]({trend['url']})"
    )


def render_markdown(payload: dict) -> str:
    stats = payload["stats"]
    lines: list[str] = []
    lines.append("# Product Opportunity Scout")
    lines.append("")
    lines.append(f"Run: **{payload['generated_at']}** · "
                 f"data file: `{payload['run_date']}.json`")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    for key, value in stats.items():
        lines.append(f"| {key.replace('_', ' ')} | {value} |")
    lines.append("")
    lines.append("Scoring: `log2(distinct posts) × (1 + log2(distinct communities)) × "
                 "(1 + log2(distinct months))`, adjusted by Google Trends direction and "
                 "app-store complaint volume. A topic backed by one post scores zero, and "
                 f"nothing ranks without corroboration from at least "
                 f"{payload['config']['min_independent_sources']} independent sources.")
    lines.append("")

    lines.append("## Ranked topics")
    lines.append("")
    if not payload["topics"]:
        lines.append("_No topic met the corroboration bar this run. "
                     "See **Source failures** below for what did not return data._")
        lines.append("")
    for topic in payload["topics"]:
        counts = topic["evidence_counts"]
        breakdown = topic["score_breakdown"]
        lines.append(f"### {topic['rank']}. {topic['label']} — score {topic['score']}")
        lines.append("")
        lines.append(
            f"**Evidence:** {counts['total']} items — "
            f"Reddit {counts[SOURCE_REDDIT]}, Apple {counts[SOURCE_APPLE]}, "
            f"Google Play {counts[SOURCE_GOOGLE_PLAY]}"
        )
        lines.append("")
        lines.append(
            f"**Spread:** {breakdown['distinct_posts']} distinct posts · "
            f"{breakdown['distinct_communities']} distinct communities · "
            f"{breakdown['distinct_months']} distinct months "
            f"({', '.join(topic['months']) or 'no dates'})"
        )
        lines.append("")
        lines.append(f"**Independent sources:** {', '.join(topic['independent_sources'])}")
        lines.append("")
        lines.append(_trend_line(topic["trend"]))
        lines.append("")
        lines.append(
            f"**Score maths:** base {breakdown['base']} "
            f"× (1 {breakdown['trend_adjustment']:+.2f} trend) "
            f"× (1 {breakdown['complaint_adjustment']:+.2f} from "
            f"{breakdown['appstore_complaints']} app-store complaints) = {topic['score']}"
        )
        lines.append("")
        lines.append("<details><summary>All supporting items "
                     f"({counts['total']})</summary>")
        lines.append("")
        for item in topic["evidence"]:
            lines.append(_evidence_line(item))
            lines.append("")
        lines.append("</details>")
        lines.append("")

    if payload["unranked_topics"]:
        lines.append("## Not ranked (insufficient corroboration)")
        lines.append("")
        lines.append("| Topic | Items | Sources | Score | Why not ranked |")
        lines.append("| --- | --- | --- | --- | --- |")
        for topic in payload["unranked_topics"][:50]:
            label = topic["label"].replace("|", "\\|")
            reason = topic["unranked_reason"].replace("|", "\\|")
            lines.append(
                f"| {label} | {topic['evidence_counts']['total']} | "
                f"{len(topic['independent_sources'])} | {topic['score']} | {reason} |"
            )
        lines.append("")

    lines.append("## Source failures")
    lines.append("")
    if not payload["failures"]:
        lines.append("_None: every configured source returned data._")
    else:
        lines.append("Recorded explicitly. No gap below was filled with an estimate.")
        lines.append("")
        lines.append("| Source | Target | Stage | Error |")
        lines.append("| --- | --- | --- | --- |")
        for failure in payload["failures"]:
            lines.append(
                "| {source} | {target} | {stage} | {error} |".format(
                    source=failure["source"],
                    target=str(failure["target"]).replace("|", "\\|"),
                    stage=failure["stage"],
                    error=_one_line(str(failure["error"]), 200).replace("|", "\\|"),
                )
            )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Primary sources only — Reddit's public JSON API, Google Trends via "
                 "pytrends, and 1–2 star app-store reviews. Quotes are verbatim and every "
                 "one links to the item it came from.")
    lines.append("")
    return "\n".join(lines)


def write_markdown(payload: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "latest.md"
    path.write_text(render_markdown(payload), encoding="utf-8")
    return path
