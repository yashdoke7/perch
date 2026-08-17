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
import re

from ..memory import classes
from ..memory.schema import MemoryItem, Scored

_WORD = re.compile(r"[a-z0-9']+")

W_SIM = 0.62
W_TAG = 0.20
W_ENT = 0.10
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


def rank(candidates: list[tuple[MemoryItem, float]], question: str,
         selection: str = "") -> list[Scored]:
    query_words = _words(question) | _words(selection[:1500])

    out: list[Scored] = []
    for item, similarity in candidates:
        tags = {t.lower() for t in item.tags}
        tag_overlap = len(tags & query_words) / len(tags) if tags else 0.0

        entities = {e.lower() for e in item.entities}
        entity_hit = 1.0 if entities & query_words else 0.0

        recency = _recency(item)

        base = (W_SIM * similarity
                + W_TAG * tag_overlap
                + W_ENT * entity_hit
                + W_REC * recency)

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
