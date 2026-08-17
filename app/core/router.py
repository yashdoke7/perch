"""Intent resolution and class routing (architecture §4.3, steps 1-2).

Two decisions happen here, and getting the FIRST one right is most of the win:

    scope     does this request need memory at all?
    domain    which of the six classes could plausibly help?

"Rewrite this sentence to be shorter" needs Identity for voice and nothing else.
A large fraction of real requests are like that, and recognising it early avoids
the over-retrieval OP-Bench measures (~80% similarity even on baited queries).

The router is deliberately lexical here rather than learned. It is the cheapest
component to swap for a classifier later, and keeping it transparent means the
admission gate downstream is being tested against an honest router rather than
one tuned to flatter it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..memory import classes

_WORD = re.compile(r"[a-z0-9']+")

# Cues per class. Not an ontology -- a routing prior that the ranker refines and
# the admission gate can overrule entirely by admitting nothing.
CUES: dict[str, set[str]] = {
    "health": {
        "doctor", "medical", "medicine", "medication", "dose", "dosage", "symptom",
        "diagnosis", "prescription", "allergy", "allergic", "pain", "illness",
        "disease", "treatment", "clinic", "hospital", "appointment", "blood",
        "surgery", "therapy", "patient", "mg", "tablet", "vaccine", "infection",
    },
    "academic": {
        "college", "university", "semester", "subject", "syllabus", "unit", "exam",
        "assignment", "lecture", "professor", "course", "marks", "grade", "credit",
        "viva", "practical", "lab", "submission", "seminar", "thesis", "curriculum",
    },
    "project": {
        "code", "bug", "error", "stack", "trace", "function", "class", "module",
        "repo", "commit", "build", "deploy", "api", "database", "schema", "test",
        "architecture", "refactor", "library", "version", "exception", "compile",
        "implementation", "algorithm", "pipeline",
    },
    "career": {
        "resume", "cv", "job", "internship", "recruiter", "interview", "hiring",
        "offer", "salary", "role", "position", "application", "linkedin", "career",
        "employer", "company", "referral", "placement",
    },
    "personal": {
        "friend", "family", "birthday", "trip", "travel", "holiday", "budget",
        "rent", "money", "gift", "dinner", "weekend", "home", "flat", "wedding",
        "parents", "brother", "sister", "plan", "book", "flight",
    },
    "identity": set(),   # always eligible; see below
}

# Requests that are pure text transformation of the selection.
TRANSFORM = {
    "rewrite", "reword", "rephrase", "shorten", "lengthen", "summarise",
    "summarize", "translate", "proofread", "correct", "formal", "casual",
    "simplify", "bullet", "tone", "grammar", "spelling", "concise", "polish",
}

EXT_PROJECT = {".py", ".js", ".ts", ".rs", ".java", ".c", ".cpp", ".go", ".rb",
               ".json", ".yaml", ".yml", ".toml", ".sql", ".sh", ".tsx", ".jsx"}
EXT_DOC = {".pdf", ".docx", ".doc", ".tex", ".md"}

APP_PROJECT = {"code", "devenv", "idea64", "pycharm", "studio", "sublime",
               "nvim", "vim", "terminal", "windowsterminal", "cmd", "powershell"}


@dataclass
class Intent:
    needs_memory: bool
    eligible: list[str]
    transform_only: bool = False
    cues: dict[str, int] = field(default_factory=dict)
    note: str = ""

    def describe(self) -> str:
        if not self.needs_memory:
            return f"no memory needed ({self.note})"
        return f"eligible: {', '.join(self.eligible)}"


def resolve(question: str, selection: str = "", source_app: str = "",
            source_path: str = "") -> Intent:
    q = question.lower()
    words = set(_WORD.findall(q))

    # --- scope -------------------------------------------------------------
    # A short transform request against a selection is the commonest case in a
    # selection-triggered tool, and it wants voice, not biography.
    transform = bool(words & TRANSFORM)
    if transform and selection and len(words) <= 12:
        return Intent(
            needs_memory=True,
            eligible=["identity"],
            transform_only=True,
            note="text transform -- identity only, for voice",
        )

    # --- domain ------------------------------------------------------------
    hits: dict[str, int] = {}
    for cls_name, cues in CUES.items():
        n = len(words & cues)
        if n:
            hits[cls_name] = n

    # Source signals. Where the text came from is evidence we get for free at
    # capture time -- the same signal private-mode source rules run on.
    app = (source_app or "").lower()
    if any(a in app for a in APP_PROJECT):
        hits["project"] = hits.get("project", 0) + 2
    if source_path:
        suffix = Path(source_path).suffix.lower()
        if suffix in EXT_PROJECT:
            hits["project"] = hits.get("project", 0) + 2
        elif suffix in EXT_DOC:
            hits["academic"] = hits.get("academic", 0) + 1

    eligible = [c for c, _ in sorted(hits.items(), key=lambda kv: -kv[1])]

    # Identity is always eligible: it is small, cheap, and nearly always shapes
    # the answer. Its low floor means the gate still drops it when irrelevant.
    if "identity" not in eligible:
        eligible.append("identity")

    # Nothing matched beyond identity: a general-knowledge question.
    if len(eligible) == 1 and not selection:
        return Intent(
            needs_memory=True,
            eligible=["identity"],
            cues=hits,
            note="no domain cues -- general question",
        )

    return Intent(needs_memory=True, eligible=eligible[:4], cues=hits)
