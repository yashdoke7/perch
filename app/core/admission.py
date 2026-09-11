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


# Identity items that say HOW to write rather than WHO you are.
VOICE_TAGS = frozenset({"voice", "style", "tone", "spelling", "writing", "format"})


def is_voice(s: Scored) -> bool:
    return s.item.cls == "identity" and bool(VOICE_TAGS & {t.lower() for t in s.item.tags})


def admit(ranked: list[Scored], alpha: float | None = None,
          max_items: int | None = None,
          floors: dict[str, float] | None = None,
          voice_always: bool = False) -> Admission:
    """`floors` overrides the per-class floors -- used by E3 to fit them on
    labelled data rather than choose them (self-critique §6).

    `voice_always` is set for a pure rewrite of a selection. "Make this
    shorter" is never semantically close to "how I want answers written", so
    a similarity floor would always drop the one memory a rewrite needs. Voice
    memory is an instruction, not a fact, and §4.5's fill order already calls
    identity "small, always" -- so for rewrites it is admitted by rule, and
    the reason says so."""
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
        floor = floors[cls_name] if floors and cls_name in floors else classes.floor_for(cls_name)
        best_sim = max(s.similarity for s in group)
        best = max(s.score for s in group)

        # --- the absolute floor -------------------------------------------
        # The whole point. A class whose BEST candidate is weak contributes
        # nothing -- we do not fall back to "the best of a bad lot".
        #
        # The floor is on SEMANTIC SIMILARITY, not on the ranked score. The
        # first version floored the ranked score, which folds in tag overlap,
        # entity hits, recency and the class prior -- so a floor fitted on one
        # set of memories quietly came to require a TAG MATCH, and the seed's
        # own async-bug note (a strong semantic match, no shared tag words)
        # was refused. "Is this about the question at all?" is a question for
        # the embedder; tags and recency only decide ORDER among the memories
        # that are. It also means a ranker change no longer moves every floor.
        if best_sim < floor:
            result.classes_rejected[cls_name] = (
                f"best candidate {best_sim:.3f} < floor {floor:.2f} - contributes nothing"
            )
            for s in group:
                s.admitted = False
                s.reason = f"class below floor ({best_sim:.3f} < {floor:.2f})"
                result.dropped.append(s)
            continue

        result.classes_admitted.append(cls_name)

        # --- the margin test ----------------------------------------------
        # Inside an admitted class, an item far below that class's best is
        # filler. Filler burns budget and drives the 2x memory-over-query
        # attention distortion OP-Bench measured. The margin is on the ranked
        # score, because that is where tags and entities earn their keep.
        margin = alpha * best
        for s in group:
            if s.similarity < floor:
                s.admitted = False
                s.reason = f"below class floor ({s.similarity:.3f} < {floor:.2f})"
                result.dropped.append(s)
            elif s.score >= margin:
                s.admitted = True
                s.reason = f"similarity {s.similarity:.3f} >= floor {floor:.2f}, score {s.score:.3f} >= margin {margin:.3f}"
                result.admitted.append(s)
            else:
                s.admitted = False
                s.reason = f"below class margin ({s.score:.3f} < {margin:.3f})"
                result.dropped.append(s)

    if voice_always:
        for s in [d for d in result.dropped if is_voice(d)]:
            result.dropped.remove(s)
            s.admitted = True
            s.reason = "voice memory -- applied to every rewrite, whatever its score"
            result.admitted.append(s)
            if "identity" not in result.classes_admitted:
                result.classes_admitted.append("identity")
                result.classes_rejected.pop("identity", None)

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
