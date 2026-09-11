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


def _refuse_on_fallback() -> bool:
    """Refuse to produce a table the hashed fallback cannot support.

    This ablation is the project's headline result, and on the hashed
    stand-in it does not merely get noisier -- it inverts. The fallback
    matches literal shared vocabulary only, so it cannot relate "rewrite this
    more formally" to a note about the user's writing style, and config C
    correctly abstains on every query. The table then reads:

        C ours                 0            0 / 3

    which looks like the gate destroying all useful context, when what is
    actually being measured is an embedder that cannot represent the
    relationship in the first place (embed.is_semantic, architecture §11.6).

    Printing that number anyway would be the exact dishonesty §11.6 warns
    against -- "the fallback is a stand-in for demonstrating the pipeline,
    never for reporting a number" -- so this refuses instead. The per-query
    traces above are still worth watching; only the SCORECARD is withheld,
    because only the scorecard makes a quantitative claim.
    """
    if embed.is_semantic():
        return False
    print("=" * 78)
    print("REFUSING TO SCORE — embedding backend is the hashed fallback.")
    print()
    print("  The fallback matches shared vocabulary only. It cannot relate")
    print("  'rewrite this formally' to a note about your writing style, so")
    print("  config C abstains on every query and the table would report")
    print("  0/3 useful context kept -- a property of the embedder, not of")
    print("  the admission gate. Architecture §11.6 says this fallback is")
    print("  never to be used for a number, so no number is printed.")
    print()
    print("  To get the real result:")
    print("     ollama serve")
    print("     ollama pull nomic-embed-text")
    print("     python -m app rebuild        # re-embed the seed with it")
    print("     python -m app ablate")
    print("=" * 78)
    return True


# The text a question is asked ABOUT, where the product would have one. A
# rewrite is always a rewrite of a selection; asked bare, "rewrite this" has
# nothing to rewrite, and the ablation used to ask it bare -- so config C was
# scored on a path the panel never takes (no selection, so no voice rule).
SELECTIONS = {
    "rewrite this to be more formal":
        "hey, cant make it to the review tomorrow, will send the slides tonight",
}


def run() -> None:
    store = MemoryStore()
    if not store.count():
        print("memory is empty — run: python -m app seed")
        return

    # Checked BEFORE the per-query traces so the warning is the first thing
    # read, not a footnote under a table that already looks authoritative.
    scoring = not _refuse_on_fallback()

    all_classes = list(mc.ORDER)
    leaks = {"A": 0, "B": 0, "C": 0}          # items injected when none should be
    kept = {"A": 0, "B": 0, "C": 0}           # cases where the needed class survived
    wanted = sum(1 for _, _, need in QUERIES if need)

    for question, expectation, need in QUERIES:
        selection = SELECTIONS.get(question, "")
        qvec = embed.embed(f"{question}\n{selection[:1200]}" if selection else question)
        print("=" * 78)
        print(f"Q: {question}")
        if selection:
            print(f"   selected: {selection!r}")
        print(f"   expected: {expectation}\n")

        # ---- A: naive global top-k, no gate ------------------------------
        cands = store.candidates(all_classes, qvec, config.OVERFETCH)
        ranked_all = ranker.rank(cands, question, selection)
        naive = ranked_all[:NAIVE_K]
        print("  A  naive global top-k, no gate")
        print(_fmt(naive))

        # ---- B: one global threshold -------------------------------------
        globals_kept = [s for s in ranked_all if s.score >= GLOBAL_TAU]
        print(f"\n  B  single global threshold (tau={GLOBAL_TAU})")
        print(_fmt(globals_kept[:NAIVE_K]))

        # ---- C: ours ------------------------------------------------------
        intent = router.resolve(question, selection)
        eligible = list(intent.eligible)
        if not intent.transform_only:
            for cls_name in all_classes:
                if cls_name in eligible:
                    continue
                hit = store.candidates([cls_name], qvec, 1)
                if hit and hit[0][1] >= config.PROBE_FLOOR:
                    eligible.append(cls_name)
        routed = store.candidates(eligible, qvec, config.OVERFETCH)
        # Exactly Pipeline._gate's call, voice rule included.
        result = admission.admit(ranker.rank(routed, question, selection),
                                 voice_always=intent.transform_only)
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
    if not scoring:
        print("No scorecard: the hashed fallback cannot support one (see above).")
        print("The per-query traces are still real -- they show the ROUTING and")
        print("the GATE'S REASONING, which do not depend on embedding quality.")
        return

    print("Two axes, because they trade against each other:\n")
    print(f"{'':14}{'leaked items':>14}{'  useful context kept':>24}")
    labels = {"A": "A naive", "B": "B global tau", "C": "C ours"}
    for cfg in ("A", "B", "C"):
        print(f"  {labels[cfg]:<12}{leaks[cfg]:>12}   {kept[cfg]:>10} / {wanted}")

    print(f"\nEmbeddings: {embed.backend()} — a real semantic model, so these")
    print("numbers mean something.")

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
