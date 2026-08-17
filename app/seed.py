"""A realistic starting memory, so the pipeline can be demonstrated immediately.

One entry is deliberately a trap. `academic-college` mentions that the campus
shares a road with a MEDICAL college. It exists so that asking PERCH a medical
question reproduces exactly the failure this design was built to prevent:

    the only item in the store containing "medical" is an ACADEMIC item, the
    ranker dutifully makes it rank 1 because it is the best of what exists,
    and a naive assistant answers a health question with college details.

Run `python -m app ask "what should I ask the doctor about this medication?"`
after seeding and watch the gate refuse it.
"""

from __future__ import annotations

from .memory.schema import MemoryItem
from .memory.store import MemoryStore

SEED: list[dict] = [
    # ---------------------------------------------------------------- identity
    dict(cls="identity", title="Who I am and how I want answers written",
         tags=["voice", "style", "student"],
         entities=["PES Modern College", "SPPU"],
         body="Final-year Computer Engineering student at PES Modern College of "
              "Engineering, affiliated to Savitribai Phule Pune University. "
              "Writes plainly and dislikes padding, hedging and filler openers. "
              "Prefers British spelling. Never wants an answer that opens with "
              "'Certainly!' or restates the question before answering."),

    # ----------------------------------------------------------------- project
    dict(cls="project", title="PERCH — desktop personal AI agent",
         tags=["perch", "fyp", "windows", "tauri", "python"],
         entities=["PERCH", "Tauri", "Ollama", "Qwen3"],
         body="Final-year project. A personal AI agent that lives in the Windows "
              "background, is summoned by selection, screenshot or hotkey in any "
              "application, and edits its answer back into the document you were "
              "in. Four layers: surface, context assembly, memory, execution. "
              "Shell is Tauri v2 with a Python sidecar for the ML work."),
    dict(cls="project", title="Selection capture falls back to the clipboard",
         tags=["perch", "uiautomation", "clipboard", "os-layer"],
         entities=["UI Automation", "TextPattern", "Win32"],
         body="UI Automation cannot read the selection in every application — "
              "Electron apps and custom-drawn controls often do not implement "
              "TextPattern. The fallback is a clipboard round-trip: save the "
              "clipboard, write a sentinel, send Ctrl+C, poll until it changes, "
              "restore the original. Decided 14 August 2026 after testing."),
    dict(cls="project", title="Admission gate: ranking is relative, injection is absolute",
         tags=["perch", "retrieval", "gating", "memory"],
         entities=["MemGate", "OP-Bench"],
         body="A class whose best candidate falls below its floor contributes "
              "nothing, rather than contributing the best of a bad lot. Prior "
              "art is MemGate, which uses a learned gate and reports cross-domain "
              "leakage falling from 27.0% to 3.5%. Ours is declarative instead: "
              "typed at import, per-class floors, every drop explainable."),
    dict(cls="project", title="Async context bug in the capture worker",
         tags=["perch", "bug", "async", "threading"],
         entities=["Python", "tkinter"],
         body="The panel froze whenever a model call took more than a second, "
              "because the request ran on the tkinter main thread. Fixed on "
              "16 August 2026 by moving the pipeline call into a worker thread "
              "and marshalling the result back with root.after(0, ...)."),

    # ---------------------------------------------------------------- academic
    # ★ the trap. Note the word "medical" — the only occurrence in the store.
    dict(cls="academic", title="College, course and campus",
         tags=["college", "sppu", "semester", "campus"],
         entities=["PES Modern College", "SPPU", "Pune"],
         body="B.E. Computer Engineering, PES Modern College of Engineering, "
              "Pune, under Savitribai Phule Pune University. Currently in the "
              "final year, semester seven. The engineering campus shares its "
              "road with the group's medical college, so the area is usually "
              "referred to as the medical college side."),
    dict(cls="academic", title="Final-year project review format",
         tags=["review", "panel", "presentation", "fyp"],
         entities=["SPPU"],
         body="Project reviews are assessed by a panel of internal faculty. "
              "Base papers must be from IEEE or ACM within the last two years — "
              "arXiv-only sources are not accepted as a base paper. The panel "
              "rejects proposals that look conceptually similar to another "
              "group's, and expects a demonstrable working result."),

    # ------------------------------------------------------------------ career
    dict(cls="career", title="What I am targeting after graduation",
         tags=["placement", "backend", "ml", "internship"],
         entities=["Python", "Rust"],
         body="Targeting backend and applied-ML roles. Strongest in Python, "
              "comfortable with systems work and picking up Rust. Wants to stay "
              "in Pune or work remotely for the first role."),

    # ---------------------------------------------------------------- personal
    dict(cls="personal", title="Standing constraints",
         tags=["schedule", "budget", "travel"],
         entities=[],
         body="Vegetarian. Prefers to keep weekday evenings free for project "
              "work during the final year. Travel budget for the year is tight."),

    # NOTE: there is deliberately NO health item. That is the point.
]


def seed(store: MemoryStore | None = None) -> int:
    store = store or MemoryStore()
    n = 0
    for row in SEED:
        item = MemoryItem(source_kind="manual", **row)
        _, how = store.add(item)
        print(f"  {how:<8} [{item.cls}] {item.title}")
        n += 1
    print(f"\n{n} items in {store.root}")
    print("Now try:  python -m app ask \"what should I ask the doctor about my medication?\"")
    return n


if __name__ == "__main__":
    seed()
