"""Text utilities: verbatim quote extraction and keyword extraction.

Quote extraction only ever *selects* a span of the source text — it never
rewrites, summarises or normalises the words that end up in the output.
"""

from __future__ import annotations

import math
import re
from collections import Counter

# Words that carry no topical information, plus the vocabulary of the demand
# phrases themselves (otherwise every candidate clusters on "wish"/"app").
STOPWORDS: set[str] = set(
    """
a about above after again against all also am an and any are aren as at be because been
before being below between both but by can cant cannot could couldnt did didnt do does
doesnt doing dont down during each else ever every few for from further get got had hadnt
has hasnt have havent having he her here hers herself him himself his how however i id if
ill im in into is isnt it its itself ive just keep know let like ll me more most much must
my myself no nor not now of off on once only or other ought our ours ourselves out over own
please really same shan she should shouldnt so some someone something still such than that
thats the their theirs them themselves then there theres these they thing things this those
through to too under until up use used using very was wasnt way we well were werent what
whats when where which while who whom why will with wont would wouldnt yeah yes yet you
your yours yourself yourselves
anyone anybody anything app apps application applications tool tools something someone
make made makes making want wants wanted wish wishes wishing pay paid paying exist exists
existing find finding found looking look need needs needed recommend recommendation
recommendations suggestion suggestions question help please thanks thank advice idea ideas
does doesnt why what how there any one two edit update tldr
""".split()
)

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'+-]*")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def normalise(text: str) -> str:
    """Lowercase and flatten typographic variants for *matching only*."""
    t = text.lower()
    t = t.replace("’", "'").replace("‘", "'")
    t = t.replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", t).strip()


def find_phrase(text: str, phrases: list[str]) -> str | None:
    """Return the first phrase in ``phrases`` that occurs in ``text``."""
    hay = normalise(text)
    for phrase in phrases:
        if normalise(phrase) in hay:
            return phrase
    return None


def extract_quote(text: str, phrase: str, max_chars: int = 400) -> str:
    """Return the verbatim sentence of ``text`` containing ``phrase``.

    The returned string is a contiguous slice of the original text. If the
    sentence is longer than ``max_chars`` it is cut on a character boundary and
    marked with an explicit ellipsis so the truncation is visible; the words
    that remain are still exactly the source's own.
    """
    needle = normalise(phrase)
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        sentence = sentence.strip()
        if not sentence:
            continue
        if needle in normalise(sentence):
            if len(sentence) > max_chars:
                return sentence[:max_chars].rstrip() + " …[truncated]"
            return sentence
    flat = text.strip()
    if len(flat) > max_chars:
        return flat[:max_chars].rstrip() + " …[truncated]"
    return flat


def _undouble(word: str) -> str:
    """``splitt`` -> ``split``, ``shopp`` -> ``shop``; ``spell`` is left alone."""
    if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "lsfz":
        return word[:-1]
    return word


def stem(word: str) -> str:
    """A deliberately small suffix stemmer.

    Enough to make "splits"/"split", "bills"/"bill" and "budgeting"/"budget"
    land in the same bucket, without pulling in a linguistics dependency. It
    only ever affects matching — quotes are never stemmed.
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 5 and word.endswith("ing"):
        return _undouble(word[:-3])
    if len(word) > 4 and word.endswith("ers"):
        return word[:-3] + "er"
    if len(word) > 4 and word.endswith("ed"):
        return _undouble(word[:-2])
    if len(word) > 4 and word.endswith("es"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def token_pairs(text: str) -> list[tuple[str, str]]:
    """``(stem, surface)`` pairs for the content words of ``text``.

    The surface form is kept so labels and search keywords can be rendered as
    real words — nobody searches Google Trends for "recurr".
    """
    out: list[tuple[str, str]] = []
    for raw in _WORD_RE.findall(normalise(text)):
        word = raw.strip("'-+")
        if len(word) < 3 or word.isdigit() or word in STOPWORDS:
            continue
        stemmed = stem(word)
        if stemmed in STOPWORDS:
            continue
        out.append((stemmed, word))
    return out


def tokens(text: str) -> list[str]:
    """Stemmed content tokens of ``text``."""
    return [stemmed for stemmed, _ in token_pairs(text)]


BIGRAM_WEIGHT = 0.5


def keyword_counts(text: str, bigram_weight: float = BIGRAM_WEIGHT) -> Counter[str]:
    """Unigram + adjacent-bigram counts for clustering.

    Bigrams are kept because they are what makes a cluster label readable
    ("meal prep" says more than "meal"), but they are weighted *below* unigrams:
    two posts about the same need rarely phrase it with the same word pair, and
    at full weight the unmatched bigrams swamp the similarity. Measured on
    hand-labelled pairs, 0.5 keeps genuinely related posts an order of magnitude
    above unrelated ones.
    """
    counts, _surfaces = keyword_bag(text, bigram_weight)
    return counts


def keyword_bag(
    text: str, bigram_weight: float = BIGRAM_WEIGHT
) -> tuple[Counter[str], dict[str, Counter[str]]]:
    """Return ``(counts, surfaces)`` for ``text``.

    ``counts`` is keyed by stemmed term; ``surfaces`` maps each stemmed term to
    the original spellings it was seen as, so a cluster can be labelled in the
    words people actually used.
    """
    pairs = token_pairs(text)
    counts: Counter[str] = Counter()
    surfaces: dict[str, Counter[str]] = {}

    def note(term: str, surface: str, weight: float) -> None:
        counts[term] += weight
        surfaces.setdefault(term, Counter())[surface] += 1

    for stemmed, surface in pairs:
        note(stemmed, surface, 1.0)
    for (sa, wa), (sb, wb) in zip(pairs, pairs[1:]):
        note(f"{sa} {sb}", f"{wa} {wb}", bigram_weight)
    return counts, surfaces


def merge_surfaces(target: dict[str, Counter[str]], extra: dict[str, Counter[str]]) -> None:
    """Fold ``extra`` surface forms into ``target`` in place."""
    for term, forms in extra.items():
        target.setdefault(term, Counter()).update(forms)


def surface_for(term: str, surfaces: dict[str, Counter[str]]) -> str:
    """The most common original spelling of a stemmed ``term``."""
    forms = surfaces.get(term)
    if not forms:
        return term
    return forms.most_common(1)[0][0]


def idf_weights(docs: list[Counter[str]]) -> dict[str, float]:
    """Inverse document frequency over the candidate corpus."""
    n = max(len(docs), 1)
    df: Counter[str] = Counter()
    for doc in docs:
        for term in doc:
            df[term] += 1
    return {term: math.log(1 + n / (1 + count)) for term, count in df.items()}


def similarity(a: Counter[str], b: Counter[str], idf: dict[str, float]) -> float:
    """IDF-weighted cosine similarity of two keyword bags.

    Cosine rather than Jaccard: these bags are short and mostly disjoint, and
    Jaccard's union denominator drags a real match down towards the noise floor.
    """
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    numerator = sum(a[t] * b[t] * idf.get(t, 1.0) ** 2 for t in shared)
    norm_a = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in a.items()))
    norm_b = math.sqrt(sum((v * idf.get(t, 1.0)) ** 2 for t, v in b.items()))
    if not norm_a or not norm_b:
        return 0.0
    return numerator / (norm_a * norm_b)
