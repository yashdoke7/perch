"""Extraction prompts (architecture §3.5).

ONE CONTRACT, SIX SCHEMAS.

One vague prompt ("extract what matters about me") returns prose that cannot be
typed, tagged or gated. Six unrelated prompts are unmaintainable and produce six
incompatible formats. So the OUTPUT FORMAT is fixed and identical for all
classes, and the CLASS SCHEMA -- what the body must cover -- is selected by the
user before extraction.

The user picking the class is what makes the item typed at the source rather
than guessed, and typing at the source is what makes the admission gate
auditable instead of learned.
"""

from __future__ import annotations

from ..memory import classes

CONTRACT = """Return ONLY a YAML list. No preamble, no explanation, no code fence.
Each element must have exactly these keys:

- title: a short specific title, under 12 words
  tags: [3 to 6 lowercase single-word tags]
  entities: [proper nouns that appear: tools, places, people, organisations]
  confidence: a number between 0 and 1
  body: |
    Two to six sentences of concrete detail. Facts, decisions, numbers, dates.
    No filler, no "the user said", no restating the question.

Rules:
- One element per DISTINCT fact or decision. Do not bundle unrelated things.
- Skip anything transient: greetings, debugging chatter, things later reversed.
- If the conversation contains nothing worth keeping, return an empty list.
- Never invent. If a detail was not stated, leave it out."""


def build(cls_name: str) -> str:
    cls = classes.get(cls_name)
    if cls is None:
        raise ValueError(f"unknown class {cls_name!r}; valid: {', '.join(classes.ORDER)}")

    covers = "\n".join(f"  - {line}" for line in cls.schema)

    return f"""You are extracting durable personal memory from this conversation
for a personal AI assistant called PERCH. The user owns this memory.

CLASS: {cls.name}
This class holds: {cls.holds}

Cover these, where the conversation actually contains them:
{covers}

{CONTRACT}

Set class to "{cls.name}" for every element.

Now read everything above in this conversation and produce the YAML list."""


def build_system(cls_name: str) -> str:
    """The same contract and schema, addressed to a model we call ourselves.

    build() above ends with "read everything above in this conversation",
    because it is written to be PASTED INTO an existing chat that already
    holds the history. When PERCH drives the extraction it supplies the
    transcript itself, so that trailer would point at nothing. Everything
    else -- the contract, the per-class schema, the class pin -- is
    deliberately identical: the two paths must produce the same shape, or
    the importer needs two parsers and one of them rots.
    """
    cls = classes.get(cls_name)
    if cls is None:
        raise ValueError(f"unknown class {cls_name!r}; valid: {', '.join(classes.ORDER)}")

    covers = "\n".join(f"  - {line}" for line in cls.schema)

    return f"""You are extracting durable personal memory from a conversation
transcript for a personal AI assistant called PERCH. The user owns this memory.

CLASS: {cls.name}
This class holds: {cls.holds}

Cover these, where the transcript actually contains them:
{covers}

{CONTRACT}

Set class to "{cls.name}" for every element."""


def all_prompts() -> dict[str, str]:
    return {name: build(name) for name in classes.ORDER}


def write_prompt_files(target) -> list:
    """Write the six prompts out so the user can paste them without the app."""
    from pathlib import Path
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in all_prompts().items():
        path = target / f"extract_{name}.txt"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written
