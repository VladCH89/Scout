# Product Opportunity Scout

Finds product opportunities that are **already evidenced by real people**, from
primary data only, and refuses to rank anything a single post could have made up.

Three sources, collected every run:

| Source | What it contributes | Endpoint |
| --- | --- | --- |
| Reddit | People asking for a product that does not exist | public `.json` API, no auth |
| Google Trends | 12-month direction of the topic's main keyword | `pytrends` |
| App stores | 1–2 star reviews complaining about a missing feature | `itunes.apple.com/rss/customerreviews` + `google-play-scraper` |

## Hard rules

These are enforced in code, not just documented:

- **Everything traces to a URL.** Every evidence item stores a permalink; the
  report renders a `[source](…)` link next to every quote. An item that cannot
  be traced to a URL is dropped, and the drop is logged.
- **Quotes are verbatim.** `scout/text.py` only ever *selects* a span of the
  source text. Nothing is paraphrased, rewritten or generated. When a quote is
  too long it is cut and marked `…[truncated]`, never condensed.
- **Failures are recorded, never filled in.** If a subreddit returns nothing, or
  Google Trends rate-limits, or an app search finds no apps, that goes into the
  `failures` list of the JSON and a table in `latest.md`. There is no estimated,
  inferred or placeholder value anywhere in the output.
- **Primary data only.** Blogs, listicles and "top app ideas" articles are not
  sources and are never fetched.
- **Corroboration is required.** A topic ranks only with evidence from at least
  two independent origins (two different subreddits, or a subreddit plus an
  app's reviews). Google Trends is an adjustment, not corroboration — it reads a
  keyword's direction, it does not report anyone's demand.

## How it works

1. **Collect.** For each subreddit × demand phrase, search Reddit's `.json`
   endpoint. Reddit's search is fuzzy, so each returned post is re-checked for
   the literal phrase; posts that do not actually contain it are discarded.
2. **Cluster.** Candidates are grouped into topics by IDF-weighted cosine
   similarity over stemmed unigrams and bigrams, with the demand-phrase
   vocabulary removed so posts do not all cluster on "wish"/"app". Labels and
   search keywords are rendered back in the spellings people actually used, so
   the Trends query is "grocery bills", not "grocery bill". Deterministic — the
   same evidence always yields the same topics.
3. **Enrich.** For the strongest topics, search both app stores for the topic's
   main keyword, pull 1- and 2-star reviews, and keep the ones that literally
   complain about something missing. Then read each topic keyword's 12-month
   Google Trends direction.
4. **Score.**

   ```
   base  = log2(distinct posts) × (1 + log2(distinct communities)) × (1 + log2(distinct months))
   score = base × (1 + trend adjustment) × (1 + complaint adjustment)
   ```

   `log2(1) = 0`, so **a topic supported by a single post scores exactly zero**.
   The trend adjustment is +0.25 rising / 0 flat / −0.20 falling / 0 unknown; the
   complaint adjustment is `0.35 × log10(1 + complaints)`, capped at +0.50.
5. **Report.** A dated `findings/YYYY-MM-DD.json` with every raw evidence record,
   plus a readable `findings/latest.md` sorted by score.

## Running it

```bash
pip install -r requirements.txt
python -m scout                      # writes findings/<date>.json and findings/latest.md
python -m scout --skip-trends        # skip Trends; the skip is logged as a failure
python -m scout --out-dir /tmp/out   # write somewhere else
python -m scout --fail-on-no-data    # exit 2 if no evidence was collected at all
```

Google Trends rate-limits unauthenticated callers hard; a `429` there is normal
and shows up in the failures table with the direction left `unknown`.

## Configuration

`config.json` overrides any key in `scout/config.py` (`DEFAULTS`). An unknown key
is an error rather than a silent no-op. The usual things to change:

- `subreddits` — the communities to search.
- `demand_phrases` — the signals to search for.
- `min_independent_sources` — the corroboration bar (default 2).
- `cluster_similarity_threshold` — raise it for tighter topics, lower for broader
  (default `0.08`, tuned on hand-labelled post pairs).
- `appstore_max_topics` / `trends_max_topics` — per-source request budgets.

## Schedule

`.github/workflows/scout.yml` runs every **Monday 06:00 UTC** (and on demand),
runs the tests, runs the scout, writes the report into the job summary, uploads
`findings/` as an artifact, and commits the results back to the branch.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

The suite covers quote extraction, clustering, the scoring rules (single post →
zero, corroboration gate, sort order), and an end-to-end run against fixture
payloads shaped like real Reddit and iTunes responses.

## Layout

```
scout/
  main.py          CLI: collect → cluster → enrich → score → report
  config.py        defaults + config.json loading
  models.py        Evidence / Failure / TrendReading records
  text.py          verbatim quote extraction, keywords, similarity
  cluster.py       greedy IDF-weighted clustering
  score.py         the scoring formula and the corroboration gate
  report.py        dated JSON + latest.md rendering
  failures.py      explicit failure recording
  http.py          HTTP with a real User-Agent and bounded retries
  sources/
    reddit.py      public .json search, phrase-verified
    trends.py      pytrends 12-month direction
    appstore.py    Apple RSS + Google Play 1–2 star complaints
findings/          output, committed by the workflow
```
