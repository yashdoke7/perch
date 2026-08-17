"""★ The admission scorer (architecture §4.4).

    Ranking is relative. Injection must be absolute.

This is the module that answers the failure case the whole retrieval design was
built around:

    A health question arrives. Health memory is empty. The only item in the
    store mentioning "medical" is an ACADEMIC item -- "B.E. Computer
    Engineering, PES Modern College". The ranker dutifully makes it rank 1,
    because it is the best of what exists.

    A naive system injects the college. The correct answer is to inject
    NOTHING and say so.

Prior art, cited honestly because we did not invent gating:
  - MemGate (arXiv 2606.06054) calls this contextual admissibility and reports
    cross-domain leakage falling 27.0% -> 3.5% with a LEARNED gate.
  - CRAG uses a retrieval evaluator with a relevance threshold.
  - OP-Bench (arXiv 2601.13722) measures the damage when nobody does this:
    memory-augmented systems score 26.2-61.1% WORSE than memory-free ones.

What is ours is that the gate is DECLARATIVE rather than learned. The class is
assigned at import time by the user, the floor is per class, and every drop
carries a human-readable reason. A learned gate cannot tell you why it dropped
your memory; a personal agent has to be able to.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import config
from ..memory import classes
from ..memory.schema import Scored


@dataclass
class Admission:
    admitted: list[Scored] = field(default_factory=list)
    dropped: list[Scored] = field(default_factory=list)
    classes_admitted: list[str] = field(default_factory=list)
    classes_rejected: dict[str, str] = field(default_factory=dict)
    abstained: bool = False

    @property
    def forces_local(self) -> bool:
        """Admitting a private-class item routes the whole request locally.

        The type system already knows which memory is sensitive, so privacy
        falls out of Part III for free -- one primitive doing two jobs.
        """
        return any(classes.is_private_class(s.item.cls) for s in self.admitted)

    def private_classes(self) -> list[str]:
        return sorted({s.item.cls for s in self.admitted
                       if classes.is_private_class(s.item.cls)})

    def report(self) -> list[str]:
        lines = []
        for cls_name, why in self.classes_rejected.items():
            lines.append(f"  class {cls_name}: {why}")
        for s in self.admitted:
            lines.append("  " + s.explain())
        for s in self.dropped[:6]:
            lines.append("  " + s.explain())
        if self.abstained:
            lines.append("  ABSTAIN - no class cleared its floor")
        return lines


def admit(ranked: list[Scored], alpha: float | None = None,
          max_items: int | None = None) -> Admission:
    alpha = config.MARGIN_ALPHA if alpha is None else alpha
    max_items = config.MAX_ITEMS if max_items is None else max_items

    result = Admission()
    if not ranked:
        result.abstained = True
        return result

    by_class: dict[str, list[Scored]] = {}
    for s in ranked:
        by_class.setdefault(s.item.cls, []).append(s)

    for cls_name, group in by_class.items():
        floor = classes.floor_for(cls_name)
        best = max(s.score for s in group)

        # --- the absolute floor -------------------------------------------
        # The whole point. A class whose BEST candidate is weak contributes
        # nothing -- we do not fall back to "the best of a bad lot".
        if best < floor:
            result.classes_rejected[cls_name] = (
                f"best candidate {best:.3f} < floor {floor:.2f} - contributes nothing"
            )
            for s in group:
                s.admitted = False
                s.reason = f"class below floor ({best:.3f} < {floor:.2f})"
                result.dropped.append(s)
            continue

        result.classes_admitted.append(cls_name)

        # --- the margin test ----------------------------------------------
        # Inside an admitted class, an item far below that class's best is
        # filler. Filler burns budget and drives the 2x memory-over-query
        # attention distortion OP-Bench measured.
        cutoff = max(floor, alpha * best)
        for s in group:
            if s.score >= cutoff:
                s.admitted = True
                s.reason = f"score {s.score:.3f} >= cutoff {cutoff:.3f}"
                result.admitted.append(s)
            else:
                s.admitted = False
                s.reason = f"below class margin ({s.score:.3f} < {cutoff:.3f})"
                result.dropped.append(s)

    result.admitted.sort(key=lambda s: -s.score)

    if len(result.admitted) > max_items:
        for s in result.admitted[max_items:]:
            s.admitted = False
            s.reason = f"beyond max_items={max_items}"
            result.dropped.append(s)
        result.admitted = result.admitted[:max_items]

    # --- abstention --------------------------------------------------------
    # Not an error state. Saying "I have nothing stored about this" is the
    # correct answer, and LongMemEval scores abstention as an ability.
    result.abstained = not result.admitted
    return result
