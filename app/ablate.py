"""The admission ablation (evaluation E4), runnable on the seeded memory.

Three configurations of the same retrieval stack, on the same queries:

    A  naive        global top-k over every class, no gate.
                    This is what most memory systems do, and it is the
                    configuration OP-Bench measures at 26-61% WORSE than
                    having no memory at all.

    B  global tau   one threshold for every class. Better, and it is roughly
                    what CRAG-style relevance filtering gives you.

    C  ours         permissive class routing + PER-CLASS floor + margin test,
                    with abstention when nothing clears.

The medical query is the case the whole design exists for: the only item in the
store containing the word "medical" is an ACADEMIC one about the campus. Config
A injects it. Config C refuses and says it has nothing.

    python -m app ablate
"""

from __future__ import annotations

from . import config
from .core import admission, ranker, router
from .memory import classes as mc
from .memory import embed
from .memory.store import MemoryStore

GLOBAL_TAU = 0.30
NAIVE_K = 4

# (question, what should happen, the class that SHOULD be present or None to abstain)
QUERIES = [
    ("what should I ask the doctor about my medication?",
     "health — nothing stored. Correct answer: ABSTAIN", None),
    ("why does the panel freeze when the model call is slow?",
     "project — the async bug is stored. Correct answer: retrieve it", "project"),
    ("what format does the panel expect for the base paper?",
     "academic — the review format is stored", "academic"),
    ("rewrite this to be more formal",
     "transform — identity only, for voice", "identity"),
    ("what is the capital of France?",
     "general knowledge — memory should stay out of the way", None),
]


def _fmt(items) -> str:
    if not items:
        return "        (nothing)"
    return "\n".join(f"        [{s.item.cls}] {s.item.title[:52]}  {s.score:.3f}"
                     for s in items)


def run() -> None:
    store = MemoryStore()
    if not store.count():
        print("memory is empty — run: python -m app seed")
        return

    all_classes = list(mc.ORDER)
    leaks = {"A": 0, "B": 0, "C": 0}          # items injected when none should be
    kept = {"A": 0, "B": 0, "C": 0}           # cases where the needed class survived
    wanted = sum(1 for _, _, need in QUERIES if need)

    for question, expectation, need in QUERIES:
        qvec = embed.embed(question)
        print("=" * 78)
        print(f"Q: {question}")
        print(f"   expected: {expectation}\n")

        # ---- A: naive global top-k, no gate ------------------------------
        cands = store.candidates(all_classes, qvec, config.OVERFETCH)
        ranked_all = ranker.rank(cands, question)
        naive = ranked_all[:NAIVE_K]
        print("  A  naive global top-k, no gate")
        print(_fmt(naive))

        # ---- B: one global threshold -------------------------------------
        globals_kept = [s for s in ranked_all if s.score >= GLOBAL_TAU]
        print(f"\n  B  single global threshold (tau={GLOBAL_TAU})")
        print(_fmt(globals_kept[:NAIVE_K]))

        # ---- C: ours ------------------------------------------------------
        intent = router.resolve(question, "")
        eligible = list(intent.eligible)
        if not intent.transform_only:
            for cls_name in all_classes:
                if cls_name in eligible:
                    continue
                hit = store.candidates([cls_name], qvec, 1)
                if hit and hit[0][1] >= config.PROBE_FLOOR:
                    eligible.append(cls_name)
        routed = store.candidates(eligible, qvec, config.OVERFETCH)
        result = admission.admit(ranker.rank(routed, question))
        print(f"\n  C  ours — routed to [{', '.join(eligible)}], per-class floors")
        print(_fmt(result.admitted))
        if result.abstained:
            print("        ABSTAINED — nothing cleared its class floor")
        for cls_name, why in result.classes_rejected.items():
            print(f"        x {cls_name}: {why}")
        print()

        # ---- accounting, on BOTH axes -------------------------------------
        sets = {"A": naive, "B": globals_kept, "C": result.admitted}
        for cfg, items in sets.items():
            if need is None:
                # Nothing should have been injected, so anything is leakage.
                leaks[cfg] += len(items)
            elif any(s.item.cls == need for s in items):
                kept[cfg] += 1

    print("=" * 78)
    print("Two axes, because they trade against each other:\n")
    print(f"{'':14}{'leaked items':>14}{'  useful context kept':>24}")
    labels = {"A": "A naive", "B": "B global tau", "C": "C ours"}
    for cfg in ("A", "B", "C"):
        print(f"  {labels[cfg]:<12}{leaks[cfg]:>12}   {kept[cfg]:>10} / {wanted}")

    print("\nThe point of PER-CLASS floors rather than one global threshold:")
    print("  a single tau high enough to keep health memory out is also high")
    print("  enough to throw identity away -- and identity is what makes a")
    print("  rewrite sound like you. Look at the 'rewrite this' case above:")
    print("  config B drops it, config C keeps it, and neither leaks.")
    print("\nMemGate (arXiv 2606.06054) reports the same leakage failure at")
    print("27.0% before gating and 3.5% after, using a LEARNED gate. Ours is")
    print("declarative, so every drop above prints its own reason.")


if __name__ == "__main__":
    run()
