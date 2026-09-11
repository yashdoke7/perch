"""The ranker (architecture §4.3, step 4).

Orders candidates by usefulness to THIS question. Five signals:

    similarity     semantic match against question + selection
    tag overlap    the refinement the class/tag split buys us
    entity hit     a named thing appearing in both
    recency/use    recent and repeatedly-useful items rank higher
    class prior    identity is cheap and near-always useful; personal
                   rarely helps a stack trace

The critical property, and the reason admission.py exists as a separate module:

    THE RANKER PRODUCES AN ORDER. AN ORDER SAYS NOTHING ABOUT WHETHER
    THE BEST ITEM IS ANY GOOD.

Ranking is relative. Injection has to be absolute. Keeping the two concerns in
separate files makes it hard to accidentally conflate them later.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from collections import Counter

from ..memory import classes
from ..memory.schema import MemoryItem, Scored

_WORD = re.compile(r"[a-z0-9']+")

# Relevance signals. They sum to 1, so a candidate that matches on nothing
# scores 0 -- not a floor-sized constant.
W_SIM = 0.67
W_TAG = 0.22
W_ENT = 0.11

# Recency and use MODULATE relevance; they do not add to it. As an additive
# term (the first version) every memory, however unrelated, collected a free
# 0.08 -- and an identity item with zero similarity cleared the identity floor
# on "what is the capital of France?". A memory cannot become relevant by
# being recent. Measured on the E3 persona benchmark, 10 Sept 2026.
W_REC = 0.08

HALF_LIFE_DAYS = 120.0


def _words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) > 2}


def _recency(item: MemoryItem) -> float:
    try:
        updated = dt.date.fromisoformat(item.updated)
    except ValueError:
        return 0.5
    age = max(0, (dt.date.today() - updated).days)
    decay = 0.5 ** (age / HALF_LIFE_DAYS)
    use_bonus = min(0.35, 0.07 * item.uses)
    return min(1.0, decay + use_bonus)


def _idf(sets: list[set[str]]) -> dict[str, float]:
    """Weight of each tag or entity WITHIN THIS CANDIDATE SET, in (0, 1].

    A tag every candidate carries says nothing about which one the question
    wants. Unweighted, the project tag "tidewatch" -- on 10 of 14 project items
    -- lifted all ten on any Tidewatch question, and "who works on Tidewatch?"
    admitted eleven memories to answer with one.
    """
    n = len(sets)
    df = Counter(v for s in sets for v in s)
    return {v: math.log(1 + n / c) / math.log(1 + n) for v, c in df.items()}


def rank(candidates: list[tuple[MemoryItem, float]], question: str,
         selection: str = "") -> list[Scored]:
    query_words = _words(question) | _words(selection[:1500])
    tag_sets = [{t.lower() for t in item.tags} for item, _ in candidates]
    ent_sets = [{e.lower() for e in item.entities} for item, _ in candidates]
    tag_w, ent_w = _idf(tag_sets), _idf(ent_sets)

    out: list[Scored] = []
    for (item, similarity), tags, entities in zip(candidates, tag_sets, ent_sets):
        tag_overlap = (sum(tag_w[t] for t in tags & query_words) / len(tags)
                       if tags else 0.0)
        entity_hit = max((ent_w[e] for e in entities & query_words), default=0.0)

        recency = _recency(item)

        relevance = W_SIM * similarity + W_TAG * tag_overlap + W_ENT * entity_hit
        base = relevance * (1.0 - W_REC + W_REC * recency)

        score = base * classes.prior_for(item.cls)

        out.append(Scored(
            item=item,
            similarity=similarity,
            tag_overlap=tag_overlap,
            entity_hit=entity_hit,
            recency=recency,
            score=round(min(1.0, score), 4),
        ))

    out.sort(key=lambda s: -s.score)
    return out
