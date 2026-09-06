"""E4 — the admission-gate ablation (Contribution 2).

This experiment already existed as `python -m app ablate`, which the README
points at as the place to start. It is NOT reimplemented here: the harness
runs the same code, so the number quoted in an evaluation report and the
number a reader gets from the documented command cannot drift apart.

Its own refusal rule applies unchanged -- on the hashed fallback embedder the
ablation inverts (config C abstains on everything and scores 0/3, a property
of the embedder rather than of the gate), so it declines to produce a
scorecard. The harness inherits that refusal rather than working around it.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from ..memory import embed
from ..memory.store import MemoryStore
from .harness import Result, unavailable

CLAIM = ("C2 -- declarative per-class admission: cross-domain leakage stopped "
         "without throwing identity away")


def run() -> Result:
    store = MemoryStore()
    if not store.count():
        return unavailable("E4", "Admission-gate ablation", CLAIM,
                           "memory is empty -- run: python -m app seed")

    if not embed.is_semantic():
        return unavailable(
            "E4", "Admission-gate ablation", CLAIM,
            f"the embedding backend is {embed.backend()!r}, the hashed fallback. "
            "It matches literal\n           shared vocabulary only, so config C "
            "abstains on every query and would score\n           0/3 -- a "
            "property of the embedder, not of the gate (§11.6). "
            "`python -m app ablate`\n           still prints the per-query "
            "routing and gate reasoning, which do not depend on\n           "
            "embedding quality. To score it: ollama serve && ollama pull "
            "nomic-embed-text\n           && python -m app rebuild")

    from ..ablate import run as run_ablation
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        run_ablation()

    lines = buffer.getvalue().splitlines()
    verdict = ""
    for line in lines:
        if line.strip().startswith("C ours"):
            verdict = (f"config C: {line.strip()} "
                       "(leaked items | useful context kept). MemGate reports "
                       "27.0% -> 3.5% with a learned gate as the reference.")
    return Result(name="E4", title="Admission-gate ablation", claim=CLAIM,
                  lines=lines, verdict=verdict)
