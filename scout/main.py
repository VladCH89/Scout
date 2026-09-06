"""Entry point: collect → cluster → enrich → score → report."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .cluster import cluster
from .config import load_config
from .failures import FailureLog
from .models import SOURCE_APPLE, SOURCE_GOOGLE_PLAY, SOURCE_REDDIT
from .report import build_payload, write_json, write_markdown
from .score import apply_ranking
from .sources import appstore, reddit, trends

log = logging.getLogger("scout")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m scout",
        description="Find validated product opportunities from primary data only.",
    )
    parser.add_argument("--config", default="config.json",
                        help="path to a JSON config file (default: config.json)")
    parser.add_argument("--out-dir", default=None,
                        help="output directory (default: the config's output_dir)")
    parser.add_argument("--skip-trends", action="store_true",
                        help="skip Google Trends; the skip is recorded as a failure")
    parser.add_argument("--skip-appstore", action="store_true",
                        help="skip app-store reviews; the skip is recorded as a failure")
    parser.add_argument("--fail-on-no-data", action="store_true",
                        help="exit non-zero when no candidate evidence was collected")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    cfg = load_config(config_path if config_path.exists() else None)
    if not config_path.exists():
        log.info("no config file at %s; using built-in defaults", config_path)
    if args.skip_trends:
        cfg["trends_enabled"] = False
    if args.skip_appstore:
        cfg["appstore_enabled"] = False

    out_dir = Path(args.out_dir or cfg["output_dir"])
    failures = FailureLog()

    log.info("scout %s: searching %d subreddits for %d demand phrases",
             __version__, len(cfg["subreddits"]), len(cfg["demand_phrases"]))
    candidates = reddit.collect(cfg, failures)
    log.info("collected %d verified reddit candidates", len(candidates))

    topics = cluster(candidates, float(cfg["cluster_similarity_threshold"]))
    log.info("clustered into %d topics", len(topics))

    # Enrich the most-supported topics first so the per-source budgets are
    # spent where the evidence already is.
    topics.sort(key=lambda t: (-len({e.item_id for e in t.evidence}),
                               -len(t.origins), t.topic_id))

    appstore_added = appstore.annotate(topics, cfg, failures)
    log.info("added %d app-store complaint items", appstore_added)

    trends.annotate(topics, cfg, failures)

    ranked, unranked = apply_ranking(topics, cfg)
    limit = int(cfg["max_topics_in_report"])
    if len(ranked) > limit:
        log.info("reporting the top %d of %d ranked topics", limit, len(ranked))
        ranked = ranked[:limit]

    def total(source: str) -> int:
        return sum(1 for t in topics for e in t.evidence if e.source == source)

    stats = {
        "reddit_evidence_items": total(SOURCE_REDDIT),
        "apple_evidence_items": total(SOURCE_APPLE),
        "google_play_evidence_items": total(SOURCE_GOOGLE_PLAY),
        "topics_found": len(topics),
        "topics_ranked": len(ranked),
        "topics_unranked": len(unranked),
        "source_failures": len(failures),
        "scout_version": __version__,
    }

    payload = build_payload(ranked, unranked, failures, cfg, stats)
    json_path = write_json(payload, out_dir)
    md_path = write_markdown(payload, out_dir)
    log.info("wrote %s and %s", json_path, md_path)

    for line in (f"{key}: {value}" for key, value in stats.items()):
        log.info("  %s", line)

    if not candidates and args.fail_on_no_data:
        log.error("no candidate evidence collected; see the failures section of %s", md_path)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        return run(args)
    except KeyboardInterrupt:
        log.error("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
