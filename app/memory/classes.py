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
        # Low floor: identity is broad by nature and should be admitted easily.
        # Calibrated against nomic-embed-text + this class's own 1.25x prior:
        # measured 0.125 (ranked score) for a genuinely unrelated query against
        # 0.230 for a real voice/style match (a "rewrite this" transform
        # request) -- 0.20 sits between them with margin on both sides. See
        # embed.relevance() for why the floor is interpreted post-calibration
        # rather than as a raw cosine number.
        floor=0.20,
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
        floor=0.30,
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
        floor=0.30,
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
        floor=0.30,
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
    # Health and Personal sit higher because a wrong admission here is the
    # cross-domain leakage OP-Bench measures -- and because admitting either
    # forces the request local, which the user should not trigger by accident.
    "health": MemoryClass(
        name="health",
        holds="conditions, medications, allergies, appointments, reports",
        floor=0.42,
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
        floor=0.38,
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
