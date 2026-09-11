"""The evaluation harness (architecture Part X).

    python -m app eval            run everything that can run here
    python -m app eval e2         run one experiment

Part X lists seven experiments. Four of them can be run on any machine with
this repository and nothing else; three cannot, and the harness says so rather
than leaving a blank the reader fills in optimistically.

    E1  over-personalisation      OP-style probe (OP-Bench is unreleased), ~15 min
    E2  budget assembly (C1)      needs nothing             ★ runs
    E3  retrieval quality         needs LongMemEval/LoCoMo  NOT RUNNABLE HERE
    E4  admission gate (C2)       needs a real embedder     runs when one is live
    E5  privacy: zero egress      needs nothing             ★ runs
    E6  latency                   stages: nothing; generation: a model
    E7  UIA coverage              needs a human at a Windows desktop

**Why an unavailable experiment is reported rather than skipped silently.**
The gap between "we did not measure this" and "we measured this and it was
fine" is the entire difference between an evaluation and a claim. A harness
that prints only what it managed to run teaches the reader that the list is
complete. This one prints all seven every time, with the three that did not
run marked and explained, so the shape of the evidence is visible at a
glance -- which is the same principle the admission gate applies to memory
and the ablation applies to its own scorecard.
"""

from __future__ import annotations

from dataclasses import dataclass, field

STATUS_RAN = "ran"
STATUS_UNAVAILABLE = "unavailable"

_BAR = "=" * 78


@dataclass
class Result:
    name: str                       # "E2"
    title: str
    claim: str                      # what this is evidence FOR
    status: str = STATUS_RAN
    reason: str = ""                # why, when not run
    lines: list[str] = field(default_factory=list)
    verdict: str = ""               # the one-line finding, when there is one

    @property
    def ran(self) -> bool:
        return self.status == STATUS_RAN

    def render(self) -> str:
        head = f"{self.name}  {self.title}"
        out = [_BAR, head, f"      evidence for: {self.claim}", ""]
        if not self.ran:
            out.append(f"  NOT RUN -- {self.reason}")
            out.append("")
            return "\n".join(out)
        out += [f"  {ln}" for ln in self.lines]
        if self.verdict:
            out += ["", f"  => {self.verdict}"]
        out.append("")
        return "\n".join(out)


def unavailable(name: str, title: str, claim: str, reason: str) -> Result:
    return Result(name=name, title=title, claim=claim,
                  status=STATUS_UNAVAILABLE, reason=reason)


# --------------------------------------------------------- the external three

def e3_retrieval_quality() -> Result:
    return unavailable(
        "E3", "Retrieval quality", "competence against published benchmarks -- not a record claim",
        "LongMemEval (500 q, ICLR 2025) and LoCoMo (1,540 q, ACL 2024) are not "
        "vendored here.\n           Part X is already honest that these are "
        "near-saturated at 92-94%, so they\n           validate competence "
        "rather than establishing a result.")


def e7_uia_coverage() -> Result:
    return unavailable(
        "E7", "UI Automation coverage per application", "the OS-layer claim no competitor publishes",
        "Requires a human at a Windows desktop with each application open, "
        "selecting text\n           and triggering capture, because the "
        "question is whether THAT app implements\n           TextPattern. It "
        "cannot be simulated -- a mock that answers for Word tells you\n       "
        "    about the mock. `python -m app` logs the capture method per "
        "trigger, which is\n           the raw material for this table.")


# ----------------------------------------------------------------- the runner

def all_experiments() -> dict:
    """Name -> zero-argument callable. Imported lazily so that one experiment
    failing to import cannot take the whole harness down with it."""
    from . import (e1_overpersonalisation, e2_budget, e3_local, e4_admission, e5_privacy,
                   e6_latency)
    return {
        "e1": e1_overpersonalisation.run,
        "e2": e2_budget.run,
        "e3": e3_local.run,
        "e4": e4_admission.run,
        "e5": e5_privacy.run,
        "e6": e6_latency.run,
        "e7": e7_uia_coverage,
    }


def run(names: list[str] | None = None) -> list[Result]:
    experiments = all_experiments()
    if not names:
        # E1 generates and judges ~70 answers, which is ~15 minutes on a local
        # 3B model -- too slow for the default pass. The default pass shows the
        # most recent saved E1 run, clearly dated, instead of re-running it or
        # leaving the row blank.
        # E3 re-embeds two personas and refits the floors (~2 minutes), so the
        # default pass shows its most recent saved run the same way.
        from . import e1_overpersonalisation, e3_local
        experiments["e1"] = e1_overpersonalisation.last_result
        experiments["e3"] = e3_local.last_result
    wanted = [n.lower() for n in (names or experiments.keys())]

    results: list[Result] = []
    for name in wanted:
        fn = experiments.get(name)
        if fn is None:
            print(f"unknown experiment {name!r}; valid: {', '.join(experiments)}")
            continue
        try:
            results.append(fn())
        except Exception as exc:                          # noqa: BLE001
            # An experiment that crashes is a result too, and a louder one
            # than a number. It must never be mistaken for "did not apply".
            results.append(Result(
                name=name.upper(), title="(crashed)", claim="-",
                status=STATUS_UNAVAILABLE,
                reason=f"the experiment raised {type(exc).__name__}: {exc}"))
    return results


def report(results: list[Result]) -> str:
    out = [r.render() for r in results]

    ran = [r for r in results if r.ran]
    missing = [r for r in results if not r.ran]
    out.append(_BAR)
    out.append(f"{len(ran)} of {len(results)} experiments ran here.")
    if missing:
        out.append("")
        out.append("Not run, and why it matters that this is stated:")
        for r in missing:
            first = r.reason.splitlines()[0]
            out.append(f"  {r.name}  {first}")
        out.append("")
        out.append("An evaluation is defined as much by what it did not measure as by")
        out.append("what it did. Nothing above is a PERCH result unless it says it ran.")
    return "\n".join(out)
