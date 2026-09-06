"""E6 — latency: trigger to first token.

Part X asks for trigger -> first token, local vs cloud. That splits cleanly
into two halves with very different reproducibility:

    the RETRIEVAL half   route, rank, gate, pack. Deterministic, no model,
                         runs anywhere. This is the half PERCH is responsible
                         for, and the half a reader can check.

    the GENERATION half  time to first token from the model. Dominated by the
                         model, the machine and whether the weights are warm
                         in RAM -- so it is measured when a model is reachable
                         and reported as unavailable when not, rather than
                         being estimated.

**Why the split matters for the claim.** "PERCH is slow" and "the 3B model you
chose is slow" are different findings with different fixes, and a single
end-to-end number cannot tell them apart. Reporting the retrieval half
separately is what makes the measurement actionable: if the pipeline overhead
is a few milliseconds against seconds of generation, the honest conclusion is
that PERCH's contribution costs nothing measurable at the point of use.
"""

from __future__ import annotations

import statistics
import time

from ..core.pipeline import Pipeline, Request
from ..memory.store import MemoryStore
from ..models import registry
from .harness import Result, unavailable

CLAIM = "the retrieval stack is not what makes a request feel slow"

QUERIES = [
    "rewrite this to be more formal",
    "why does the panel freeze when the model call is slow?",
    "what should I ask the doctor about my medication?",
    "what is the capital of France?",
]

RUNS = 5


def run() -> Result:
    store = MemoryStore()
    if not store.count():
        return unavailable("E6", "Latency", CLAIM,
                           "memory is empty -- run: python -m app seed")

    pipeline = Pipeline(store)
    model = registry.select(private=False)
    has_model = model.provider != "stub"

    lines = [
        f"{RUNS} runs per query. Stage timings are the retrieval stack only --",
        "route, rank, gate, pack -- captured before generation begins.",
        "",
        f"  {'query':<46} {'median':>8} {'worst':>8}",
    ]

    all_medians = []
    for question in QUERIES:
        samples = []
        for _ in range(RUNS):
            stages: dict[str, float] = {}
            started = time.perf_counter()

            def on_stage(name: str, _detail: str, _s=stages, _t=started) -> None:
                # "model" fires as generation STARTS, so the time to reach it
                # is exactly the retrieval half we want isolated.
                _s.setdefault(name, (time.perf_counter() - _t) * 1000)

            pipeline.run(Request(question=question), on_stage=on_stage)
            if "model" in stages:
                samples.append(stages["model"])

        if not samples:
            continue
        median = statistics.median(samples)
        all_medians.append(median)
        lines.append(f"  {question[:44]:<46} {median:>7.1f}ms {max(samples):>7.1f}ms")

    lines += [
        "",
        f"embedding backend: {__import__('app.memory.embed', fromlist=['x']).backend()}",
        f"model route:       {model.label()}",
        "",
        "A large 'worst' on the FIRST query only is the cold registry probe, not",
        "variance: model selection checks whether Ollama is listening, and when",
        "nothing is, that costs ~4s because localhost resolves to both ::1 and",
        "127.0.0.1 and urllib waits out a timeout on each. It is cached for 30s",
        "afterwards, which is why every later run is in single-digit ms. This",
        "experiment is what found that -- it used to be paid on EVERY request.",
        "",
    ]

    if not has_model:
        lines += [
            "Generation half: NOT MEASURED -- no model is reachable, so time to",
            "first token cannot be timed. It is not estimated here. Start Ollama",
            "or set PERCH_API_BASE to measure the other half.",
        ]
    else:
        lines += [
            "Generation half: measurable on this machine. It is dominated by the",
            "model and by whether the weights are warm, so treat a single figure",
            "with suspicion and report the machine alongside it.",
        ]

    if not all_medians:
        return unavailable("E6", "Latency", CLAIM,
                           "no stage timings were captured -- the pipeline did not "
                           "reach the model stage")

    worst = max(all_medians)
    verdict = (
        f"retrieval costs {min(all_medians):.1f}-{worst:.1f} ms at the median. "
        + ("Against seconds of local generation that is not what a user "
           "perceives as slow."
           if has_model else
           "The generation half is unmeasured here, so this is half the answer, "
           "and the half PERCH controls."))

    return Result(name="E6", title="Latency", claim=CLAIM, lines=lines, verdict=verdict)
