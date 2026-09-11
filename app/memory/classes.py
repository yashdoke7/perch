"""The six memory classes (architecture §3.2).

Design rule: FEW CLASSES, MANY TAGS.

A class is a routing decision, and every class we add is another chance for the
router to be wrong -- router error being the exact failure the admission gate
exists to prevent. Fine distinctions therefore live in tags, which only reorder
results inside an already-chosen class and cannot cause a routing miss.

Each class carries four things the pipeline needs:

    floor        tau_c -- the ABSOLUTE admission threshold (§4.4). Calibrated per
                 class because classes differ in how tightly they cluster.
    private      whether items of this class force local execution (§7.3)
    prior        a ranking nudge; Identity is cheap and nearly always useful,
                 Personal rarely helps a stack trace
    schema       what an extraction prompt must cover for this class (§3.5)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MemoryClass:
    name: str
    holds: str
    floor: float
    private: bool
    prior: float
    schema: list[str] = field(default_factory=list)
    cap: int = 400          # per-class item ceiling; memory growth is bounded


CLASSES: dict[str, MemoryClass] = {
    "identity": MemoryClass(
        name="identity",
        holds="who you are, how you want answers written, standing instructions",
        # FITTED, not chosen (self-critique §6): every floor below comes from
        # E3's development persona (68 memories, 112 labelled questions,
        # nomic-embed-text) and was then scored, unchanged, on a held-out
        # persona it never saw. Floors compare against calibrated SEMANTIC
        # SIMILARITY (admission.py says why), so a ranker change leaves them
        # alone -- but a different embedder needs a refit: python -m app eval e3
        #
        # Identity rose from a hand-set 0.20: at that value voice and schedule
        # notes rode into unrelated questions. Rewrites do not depend on it --
        # voice memory is admitted by rule for those (admission.VOICE_TAGS).
        floor=0.26,
        private=False,
        prior=1.25,
        cap=40,
        schema=[
            "role and current position",
            "institution or employer",
            "languages and spelling convention",
            "stated writing preferences: tone, length, things never to write",
            "standing instructions that apply to every answer",
        ],
    ),
    "project": MemoryClass(
        name="project",
        holds="bounded work: purpose, stack, decisions, problems, timeline, results",
        # The least stable of the six across CV folds (0.34-0.56): a project's
        # items share a topic and cluster tightly, so the margin test, not the
        # floor, is what stops "who works on X?" admitting all of project X.
        floor=0.34,
        private=False,
        prior=1.10,
        schema=[
            "name and one-line purpose, and the problem it solves",
            "stack, tools and versions",
            "architecture and pipeline decisions AND the reason each was chosen",
            "problems hit during design AND how each was resolved",
            "timeline: what happened when",
            "results, numbers, benchmarks achieved",
            "what remains, and known limitations",
        ],
    ),
    "academic": MemoryClass(
        name="academic",
        holds="institution, semester, subjects, formats, deadlines, conventions",
        floor=0.46,
        private=False,
        prior=1.00,
        schema=[
            "institution, course, semester and year",
            "subjects and their unit breakdown",
            "assessment format and weighting",
            "submission and formatting conventions",
            "deadlines and important dates",
        ],
    ),
    "career": MemoryClass(
        name="career",
        holds="roles, skills, applications, interviews, targets",
        floor=0.36,
        private=False,
        prior=1.00,
        schema=[
            "roles held, with dates and responsibilities",
            "skills, and the evidence for each",
            "applications made and their outcomes",
            "interview experiences and questions asked",
            "target roles, companies and constraints",
        ],
    ),
    # Health and Personal were hand-set HIGHER (0.42, 0.38), on the reasoning
    # that a wrong admission here is the leakage OP-Bench measures. Measured,
    # that bought nothing: the leaks were already stopped upstream -- the
    # router only makes these classes eligible on health/personal cues or a
    # semantic probe, and the margin test does the rest -- while the high
    # floor dropped real answers ("what triggers my migraines?" drew nothing).
    # Fitted lower, E3 still records ZERO private leaks on the held-out
    # persona. Admitting either still forces the request local.
    "health": MemoryClass(
        name="health",
        holds="conditions, medications, allergies, appointments, reports",
        floor=0.28,
        private=True,
        prior=0.95,
        cap=200,
        schema=[
            "diagnosed conditions, with dates",
            "current medications and dosages",
            "known allergies and adverse reactions",
            "appointments, practitioners and specialisms",
            "test results and reports, with dates",
        ],
    ),
    "personal": MemoryClass(
        name="personal",
        holds="relationships, preferences, finances, travel, home, commitments",
        floor=0.32,
        private=True,
        prior=0.90,
        schema=[
            "people, relationships and how you refer to them",
            "preferences and constraints: dietary, accessibility, scheduling",
            "recurring commitments",
            "financial constraints relevant to decisions",
            "travel and home logistics",
        ],
    ),
}

# System-managed stores. These are NOT user classes: the user does not author
# them, they are capped, and they are never proposed for import.
SYSTEM_STORES = ("episodic", "working")

ORDER = ["identity", "project", "academic", "career", "health", "personal"]


def get(name: str) -> MemoryClass | None:
    return CLASSES.get(name.strip().lower())


def is_private_class(name: str) -> bool:
    cls = get(name)
    return bool(cls and cls.private)


def floor_for(name: str) -> float:
    cls = get(name)
    return cls.floor if cls else 0.35


def prior_for(name: str) -> float:
    cls = get(name)
    return cls.prior if cls else 1.0


# Classes the budget packer will not evict to make room for a tool result.
# Identity is the only one, and for the same reason §4.5's fill order lists it
# first and calls it "small, always": it is what makes an answer sound like
# the user. A search result that costs someone their own voice is a bad trade
# at any size, and identity items are small enough that protecting them frees
# almost nothing anyway.
PROTECTED_FROM_EVICTION = ("identity",)


def is_protected_from_eviction(name: str) -> bool:
    return (name or "").strip().lower() in PROTECTED_FROM_EVICTION
