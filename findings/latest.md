# Product Opportunity Scout

Run: **2026-09-21T12:38:16+00:00** · data file: `2026-09-21.json`

| Metric | Value |
| --- | --- |
| reddit evidence items | 0 |
| apple evidence items | 0 |
| google play evidence items | 0 |
| topics found | 0 |
| topics ranked | 0 |
| topics unranked | 0 |
| source failures | 42 |
| scout version | 1.0.0 |

Scoring: `log2(distinct posts) × (1 + log2(distinct communities)) × (1 + log2(distinct months))`, adjusted by Google Trends direction and app-store complaint volume. A topic backed by one post scores zero, and nothing ranks without corroboration from at least 2 independent sources.

## Ranked topics

_No topic met the corroboration bar this run. See **Source failures** below for what did not return data._

## Source failures

Recorded explicitly. No gap below was filled with an estimate.

| Source | Target | Stage | Error |
| --- | --- | --- | --- |
| reddit | r/SomebodyMakeThis :: 'is there an app' | search | HTTP 403 from https://www.reddit.com/r/SomebodyMakeThis/search.json |
| reddit | r/SomebodyMakeThis :: 'why is there no' | search | HTTP 403 from https://www.reddit.com/r/SomebodyMakeThis/search.json |
| reddit | r/SomebodyMakeThis :: 'wish there was' | search | HTTP 403 from https://www.reddit.com/r/SomebodyMakeThis/search.json |
| reddit | r/SomebodyMakeThis :: 'does anyone know a tool' | search | HTTP 403 from https://www.reddit.com/r/SomebodyMakeThis/search.json |
| reddit | r/SomebodyMakeThis :: "I'd pay for" | search | HTTP 403 from https://www.reddit.com/r/SomebodyMakeThis/search.json |
| reddit | r/SomebodyMakeThis | collect | no posts matched any demand phrase after verification |
| reddit | r/AppIdeas :: 'is there an app' | search | HTTP 403 from https://www.reddit.com/r/AppIdeas/search.json |
| reddit | r/AppIdeas :: 'why is there no' | search | HTTP 403 from https://www.reddit.com/r/AppIdeas/search.json |
| reddit | r/AppIdeas :: 'wish there was' | search | HTTP 403 from https://www.reddit.com/r/AppIdeas/search.json |
| reddit | r/AppIdeas :: 'does anyone know a tool' | search | HTTP 403 from https://www.reddit.com/r/AppIdeas/search.json |
| reddit | r/AppIdeas :: "I'd pay for" | search | HTTP 403 from https://www.reddit.com/r/AppIdeas/search.json |
| reddit | r/AppIdeas | collect | no posts matched any demand phrase after verification |
| reddit | r/productivity :: 'is there an app' | search | HTTP 403 from https://www.reddit.com/r/productivity/search.json |
| reddit | r/productivity :: 'why is there no' | search | HTTP 403 from https://www.reddit.com/r/productivity/search.json |
| reddit | r/productivity :: 'wish there was' | search | HTTP 403 from https://www.reddit.com/r/productivity/search.json |
| reddit | r/productivity :: 'does anyone know a tool' | search | HTTP 403 from https://www.reddit.com/r/productivity/search.json |
| reddit | r/productivity :: "I'd pay for" | search | HTTP 403 from https://www.reddit.com/r/productivity/search.json |
| reddit | r/productivity | collect | no posts matched any demand phrase after verification |
| reddit | r/personalfinance :: 'is there an app' | search | HTTP 403 from https://www.reddit.com/r/personalfinance/search.json |
| reddit | r/personalfinance :: 'why is there no' | search | HTTP 403 from https://www.reddit.com/r/personalfinance/search.json |
| reddit | r/personalfinance :: 'wish there was' | search | HTTP 403 from https://www.reddit.com/r/personalfinance/search.json |
| reddit | r/personalfinance :: 'does anyone know a tool' | search | HTTP 403 from https://www.reddit.com/r/personalfinance/search.json |
| reddit | r/personalfinance :: "I'd pay for" | search | HTTP 403 from https://www.reddit.com/r/personalfinance/search.json |
| reddit | r/personalfinance | collect | no posts matched any demand phrase after verification |
| reddit | r/frugal :: 'is there an app' | search | HTTP 403 from https://www.reddit.com/r/frugal/search.json |
| reddit | r/frugal :: 'why is there no' | search | HTTP 403 from https://www.reddit.com/r/frugal/search.json |
| reddit | r/frugal :: 'wish there was' | search | HTTP 403 from https://www.reddit.com/r/frugal/search.json |
| reddit | r/frugal :: 'does anyone know a tool' | search | HTTP 403 from https://www.reddit.com/r/frugal/search.json |
| reddit | r/frugal :: "I'd pay for" | search | HTTP 403 from https://www.reddit.com/r/frugal/search.json |
| reddit | r/frugal | collect | no posts matched any demand phrase after verification |
| reddit | r/smallbusiness :: 'is there an app' | search | HTTP 403 from https://www.reddit.com/r/smallbusiness/search.json |
| reddit | r/smallbusiness :: 'why is there no' | search | HTTP 403 from https://www.reddit.com/r/smallbusiness/search.json |
| reddit | r/smallbusiness :: 'wish there was' | search | HTTP 403 from https://www.reddit.com/r/smallbusiness/search.json |
| reddit | r/smallbusiness :: 'does anyone know a tool' | search | HTTP 403 from https://www.reddit.com/r/smallbusiness/search.json |
| reddit | r/smallbusiness :: "I'd pay for" | search | HTTP 403 from https://www.reddit.com/r/smallbusiness/search.json |
| reddit | r/smallbusiness | collect | no posts matched any demand phrase after verification |
| reddit | r/Entrepreneur :: 'is there an app' | search | HTTP 403 from https://www.reddit.com/r/Entrepreneur/search.json |
| reddit | r/Entrepreneur :: 'why is there no' | search | HTTP 403 from https://www.reddit.com/r/Entrepreneur/search.json |
| reddit | r/Entrepreneur :: 'wish there was' | search | HTTP 403 from https://www.reddit.com/r/Entrepreneur/search.json |
| reddit | r/Entrepreneur :: 'does anyone know a tool' | search | HTTP 403 from https://www.reddit.com/r/Entrepreneur/search.json |
| reddit | r/Entrepreneur :: "I'd pay for" | search | HTTP 403 from https://www.reddit.com/r/Entrepreneur/search.json |
| reddit | r/Entrepreneur | collect | no posts matched any demand phrase after verification |

---

Primary sources only — Reddit's public JSON API, Google Trends via pytrends, and 1–2 star app-store reviews. Quotes are verbatim and every one links to the item it came from.
