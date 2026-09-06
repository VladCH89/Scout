from scout.cluster import Topic, cluster
from scout.config import DEFAULTS
from scout.models import Evidence, TrendReading
from scout.score import apply_ranking, score_topic


def make(item_id, origin, date, source="reddit", text="shared grocery budget tracking"):
    return Evidence(
        source=source, origin=origin, quote=text, full_text=text,
        url=f"https://example.test/{item_id}", date=date, score=10,
        score_kind="upvotes", matched_phrase="wish there was", item_id=item_id,
        title=text,
    )


def topic_with(evidence):
    topic = Topic(topic_id="t001")
    for item in evidence:
        topic.add(item, __import__("collections").Counter())
    return topic


def test_single_post_scores_zero():
    topic = topic_with([make("a", "r/AppIdeas", "2026-01-04")])
    score_topic(topic, DEFAULTS)
    assert topic.score == 0.0


def test_score_grows_with_spread():
    narrow = topic_with([make("a", "r/AppIdeas", "2026-01-04"),
                         make("b", "r/AppIdeas", "2026-01-09")])
    broad = topic_with([make("a", "r/AppIdeas", "2026-01-04"),
                        make("b", "r/frugal", "2026-03-09"),
                        make("c", "r/productivity", "2026-05-01"),
                        make("d", "r/Entrepreneur", "2026-07-02")])
    score_topic(narrow, DEFAULTS)
    score_topic(broad, DEFAULTS)
    assert broad.score > narrow.score > 0


def test_trend_and_complaints_adjust_the_base():
    base_topic = topic_with([make("a", "r/AppIdeas", "2026-01-04"),
                             make("b", "r/frugal", "2026-03-09")])
    score_topic(base_topic, DEFAULTS)

    rising = topic_with([make("a", "r/AppIdeas", "2026-01-04"),
                         make("b", "r/frugal", "2026-03-09")])
    rising.trend = TrendReading("grocery budget", "rising", 40.0, 10.0, 14.0,
                                "today 12-m", "https://trends.google.com/x")
    score_topic(rising, DEFAULTS)
    assert rising.score > base_topic.score

    falling = topic_with([make("a", "r/AppIdeas", "2026-01-04"),
                          make("b", "r/frugal", "2026-03-09")])
    falling.trend = TrendReading("grocery budget", "falling", -40.0, 14.0, 10.0,
                                 "today 12-m", "https://trends.google.com/x")
    score_topic(falling, DEFAULTS)
    assert falling.score < base_topic.score

    with_complaints = topic_with([
        make("a", "r/AppIdeas", "2026-01-04"),
        make("b", "r/frugal", "2026-03-09"),
        make("c", "apple:123", "2026-04-01", source="apple_appstore"),
        make("d", "play:com.x", "2026-04-02", source="google_play"),
    ])
    score_topic(with_complaints, DEFAULTS)
    assert with_complaints.score_breakdown["appstore_complaints"] == 2
    assert with_complaints.score_breakdown["complaint_adjustment"] > 0


def test_ranking_requires_two_independent_sources():
    one_source = topic_with([make("a", "r/AppIdeas", "2026-01-04"),
                             make("b", "r/AppIdeas", "2026-03-09")])
    one_source.topic_id = "t001"
    two_sources = topic_with([make("c", "r/AppIdeas", "2026-01-04"),
                              make("d", "r/frugal", "2026-03-09")])
    two_sources.topic_id = "t002"
    ranked, unranked = apply_ranking([one_source, two_sources], DEFAULTS)
    assert [t.topic_id for t in ranked] == ["t002"]
    assert unranked[0].topic_id == "t001"
    assert "independent source" in unranked[0].unranked_reason


def test_ranked_topics_are_sorted_by_score_descending():
    topics = []
    for index, count in enumerate([2, 6, 3]):
        evidence = [make(f"{index}-{n}", f"r/sub{n}", f"2026-0{n + 1}-01")
                    for n in range(count)]
        topic = topic_with(evidence)
        topic.topic_id = f"t{index:03d}"
        topics.append(topic)
    ranked, _ = apply_ranking(topics, DEFAULTS)
    scores = [t.score for t in ranked]
    assert scores == sorted(scores, reverse=True)


def test_clustering_separates_unrelated_candidates():
    evidence = [
        make("a", "r/AppIdeas", "2026-01-04", text="app for splitting grocery bills with roommates"),
        make("b", "r/frugal", "2026-02-04", text="splitting grocery bills between roommates each week"),
        make("c", "r/smallbusiness", "2026-03-04", text="chasing late invoices from freelance clients"),
    ]
    topics = cluster(evidence, DEFAULTS["cluster_similarity_threshold"])
    grouped = {frozenset(e.item_id for e in t.evidence) for t in topics}
    assert frozenset({"a", "b"}) in grouped
    assert frozenset({"c"}) in grouped
