from scout.text import extract_quote, find_phrase, idf_weights, keyword_counts, similarity, stem

PHRASES = ["is there an app", "why is there no", "wish there was",
           "does anyone know a tool", "I'd pay for"]


def test_find_phrase_is_case_and_apostrophe_insensitive():
    assert find_phrase("Honestly I’d pay for this today", PHRASES) == "I'd pay for"
    assert find_phrase("WHY IS THERE NO decent split-bill app?", PHRASES) == "why is there no"
    assert find_phrase("just a normal post", PHRASES) is None


def test_extract_quote_returns_a_verbatim_slice():
    text = "Some intro. I wish there was a tool for shared grocery budgets. Thanks all!"
    quote = extract_quote(text, "wish there was")
    assert quote == "I wish there was a tool for shared grocery budgets."
    assert quote in text


def test_extract_quote_marks_truncation_instead_of_rewriting():
    text = "I wish there was " + "x" * 500
    quote = extract_quote(text, "wish there was", max_chars=50)
    assert quote.endswith("…[truncated]")
    assert text.startswith(quote.replace(" …[truncated]", ""))


def test_keywords_drop_the_demand_phrase_vocabulary():
    counts = keyword_counts("I wish there was an app for splitting grocery bills")
    assert "wish" not in counts and "app" not in counts
    assert "split grocery" in counts  # stemmed


def test_stemming_collapses_the_obvious_variants():
    assert stem("splits") == stem("split") == "split"
    assert stem("bills") == "bill"
    assert stem("budgeting") == "budget"
    assert stem("less") == "less"  # never strips a doubled s


def test_similarity_separates_related_from_unrelated_text():
    a = keyword_counts("splitting grocery bills with roommates")
    b = keyword_counts("grocery bill splitting between roommates")
    c = keyword_counts("invoice reminders for freelance clients")
    idf = idf_weights([a, b, c])
    assert similarity(a, b, idf) > 0.3
    assert similarity(a, c, idf) == 0.0
    assert similarity(a, b, idf) > similarity(a, c, idf)


def test_similarity_clears_the_default_threshold_for_reworded_posts():
    """Guards the tuning: differently worded posts about one need must merge."""
    from scout.config import DEFAULTS

    bags = [
        keyword_counts("I wish there was an app to split recurring grocery bills with roommates"),
        keyword_counts("Is there an app that splits grocery bills between housemates?"),
        keyword_counts("chasing late invoices from freelance clients is a nightmare"),
        keyword_counts("wish there was a tool to chase unpaid freelance invoices automatically"),
    ]
    idf = idf_weights(bags)
    threshold = DEFAULTS["cluster_similarity_threshold"]
    assert similarity(bags[0], bags[1], idf) > threshold
    assert similarity(bags[2], bags[3], idf) > threshold
    assert similarity(bags[0], bags[2], idf) < threshold
    assert similarity(bags[1], bags[3], idf) < threshold
