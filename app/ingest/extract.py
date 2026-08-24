"""Class-typed extraction from parsed sessions (architecture §3.4, §3.5).

    sessions  ->  [model, one class at a time]  ->  proposals  ->  review  ->  store

Three rules from §3.4 are enforced here rather than described:

    1. NOTHING IS STORED SILENTLY. This module returns PROPOSALS. It never
       touches the store -- review.py does, after a human says yes.
    2. THE USER PICKS THE CLASS before extraction. That is what makes an item
       typed at the source rather than guessed, and typing at the source is
       what makes the admission gate auditable instead of learned (§4.6, C2).
    3. NEAR-DUPLICATES MERGE. Handled downstream by MemoryStore.add(), which
       reports "merged" so review can tell the user what actually happened.

Why the contract is parsed by hand rather than with PyYAML:

    The output format is one we chose, so we can parse it tolerantly, and a
    tolerant parser is the RIGHT tool here -- not a shortcut. Models produce
    almost-YAML: a stray code fence, a "Here are the items:" preamble, an
    indent that slips by one space. PyYAML answers all of those with a single
    exception that loses the ENTIRE batch, including the nine items it parsed
    perfectly. This parser fails per item and keeps the rest, which is the
    behaviour §11.5 asks for -- isolated parsers that fail loudly and produce
    nothing rather than garbage. It also keeps the dependency list honest:
    schema.py already hand-rolls frontmatter for the same reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import config
from ..memory import classes as mc
from ..memory.schema import MemoryItem
from ..models import client
from ..models.registry import Model
from . import prompts
from .exports import Session

# A model asked for "two to six sentences" occasionally writes an essay. An
# item that cannot enter a prompt whole is useless to the packer (§4.5, items
# enter whole or not at all), so oversized bodies are flagged for review
# rather than stored and discovered later.
MAX_BODY_CHARS = 1500

_FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*$")
_ITEM_START = re.compile(r"^(\s*)-\s+(\w+)\s*:\s*(.*)$")
_KEY = re.compile(r"^(\s*)(\w+)\s*:\s*(.*)$")
_BLOCK_SCALAR = re.compile(r"^[|>][-+]?\d*$")


@dataclass
class Proposal:
    """One candidate memory item, plus everything review needs to judge it."""
    item: MemoryItem
    session_title: str = ""
    warnings: list[str] = field(default_factory=list)
    accepted: bool = False

    @property
    def confidence(self) -> float:
        return self.item.confidence

    def summary(self) -> str:
        return f"[{self.item.cls}] {self.item.title}"


class ExtractionUnavailable(RuntimeError):
    """Raised when no model can do this. Never a silent empty result."""


# --------------------------------------------------------------- the contract

def _strip_fences(text: str) -> str:
    """Drop code fences and any prose before the first list element.

    Models are told "no preamble, no code fence" and comply most of the time.
    The remainder is cheap to tolerate and expensive to lose.
    """
    lines = [ln for ln in text.splitlines() if not _FENCE.match(ln)]
    for i, ln in enumerate(lines):
        if _ITEM_START.match(ln):
            return "\n".join(lines[i:])
    return "\n".join(lines)


def _split_items(text: str) -> list[list[str]]:
    """Group lines into one block per list element."""
    blocks: list[list[str]] = []
    current: list[str] | None = None
    base = 0
    for line in text.splitlines():
        m = _ITEM_START.match(line)
        # A new element starts only at the same indent as the first one --
        # otherwise a "- " bullet INSIDE a body would split that item in two.
        if m and (current is None or len(m.group(1)) <= base):
            if current:
                blocks.append(current)
            base = len(m.group(1))
            # Re-write "- key: value" as "  key: value" so the block has one
            # uniform shape for the key walker below.
            current = [" " * (base + 2) + f"{m.group(2)}: {m.group(3)}"]
        elif current is not None:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _inline_list(raw: str) -> list[str]:
    return [p.strip().strip("'\"") for p in raw.strip().strip("[]").split(",") if p.strip()]


def _parse_block(lines: list[str]) -> dict:
    """Key/value pairs for one element, including block scalars."""
    fields: dict = {}
    indents = [len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()]
    base = min(indents) if indents else 0

    i = 0
    last_key: str | None = None
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = _KEY.match(line)
        if m and len(m.group(1)) == base:
            key, raw = m.group(2).lower(), m.group(3).strip()

            if _BLOCK_SCALAR.match(raw):
                # "body: |" -- consume every following more-indented line.
                body: list[str] = []
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if nxt.strip() and (len(nxt) - len(nxt.lstrip())) <= base:
                        break
                    body.append(nxt.strip())
                    i += 1
                fields[key] = "\n".join(body).strip()
                last_key = key
                continue

            if raw.startswith("["):
                fields[key] = _inline_list(raw)
            else:
                fields[key] = raw.strip("'\"")
            last_key = key
            i += 1
            continue

        # A more-indented non-key line continues the previous scalar. This is
        # how an unfenced multi-line body survives.
        if last_key and isinstance(fields.get(last_key), str):
            stripped = line.strip()
            if stripped.startswith("- "):
                # "tags:" followed by "- a" / "- b" block-style list
                existing = fields[last_key]
                fields[last_key] = ([existing] if existing else []) + [stripped[2:].strip()]
            else:
                fields[last_key] = (fields[last_key] + " " + stripped).strip()
        elif last_key and isinstance(fields.get(last_key), list):
            stripped = line.strip()
            if stripped.startswith("- "):
                fields[last_key].append(stripped[2:].strip())
        i += 1

    return fields


def parse_contract(text: str, cls_name: str, platform: str = "",
                   session_title: str = "") -> list[Proposal]:
    """Turn one model response into proposals. Bad elements are skipped, not fatal."""
    out: list[Proposal] = []
    for block in _split_items(_strip_fences(text)):
        fields = _parse_block(block)
        title = str(fields.get("title") or "").strip()
        body = fields.get("body") or ""
        if isinstance(body, list):
            body = "\n".join(body)
        body = str(body).strip()

        # The two fields without which an item is not an item. Silently
        # dropping a malformed element is fine here precisely BECAUSE the
        # user reviews the result -- they see a count, and nothing is stored.
        if not title or not body:
            continue

        try:
            confidence = float(fields.get("confidence") or 1.0)
        except (TypeError, ValueError):
            confidence = 1.0

        tags = fields.get("tags") or []
        entities = fields.get("entities") or []
        if isinstance(tags, str):
            tags = _inline_list(tags)
        if isinstance(entities, str):
            entities = _inline_list(entities)

        warnings: list[str] = []
        if len(body) > MAX_BODY_CHARS:
            warnings.append(f"body is {len(body)} chars; items enter a prompt whole (§4.5)")
        if confidence < 0.5:
            warnings.append(f"the extractor was unsure (confidence {confidence:.2f})")
        # The class is pinned by US, not read from the response. The model is
        # told to set it, but trusting that would let a bad extraction file a
        # health fact under academic -- and the class IS the privacy boundary.
        stated = str(fields.get("class") or "").strip().lower()
        if stated and stated != cls_name:
            warnings.append(f"model labelled this {stated!r}; filed as {cls_name!r}")

        out.append(Proposal(
            item=MemoryItem(
                cls=cls_name,
                title=title[:120],
                body=body,
                tags=[str(t).lower() for t in tags][:8],
                entities=[str(e) for e in entities][:8],
                source_kind="import",
                source_platform=platform,
                source_ref=session_title[:60],
                confidence=confidence,
            ),
            session_title=session_title,
            warnings=warnings,
        ))
    return out


# -------------------------------------------------------------- the extractor

def _budget_chars(model: Model) -> int:
    """How much transcript fits alongside the instructions and the answer.

    Same reserve logic as the packer, for the same reason: the number comes
    from the model's own context window, so swapping models changes this and
    nothing else (C1).
    """
    usable = model.context_window - config.RESERVE_RESPONSE - config.RESERVE_SYSTEM
    return max(2000, int(usable * config.CHARS_PER_TOKEN * 0.7))


def _chunks(session: Session, budget: int) -> list[str]:
    """Split a long session at TURN boundaries, never mid-turn.

    Cutting inside a turn is how you get an item extracted from half a
    sentence, which then reads as a confident, incomplete fact -- the same
    failure the packer's whole-items-only rule exists to prevent.
    """
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for role, text in session.turns:
        turn = f"{role.upper()}: {text.strip()}"
        if not text.strip():
            continue
        if size + len(turn) > budget and current:
            chunks.append("\n\n".join(current))
            current, size = [], 0
        current.append(turn[:budget])
        size += len(turn)
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def extract_session(session: Session, cls_name: str, model: Model) -> list[Proposal]:
    if mc.get(cls_name) is None:
        raise ValueError(f"unknown class {cls_name!r}; valid: {', '.join(mc.ORDER)}")

    system = prompts.build_system(cls_name)
    out: list[Proposal] = []
    for chunk in _chunks(session, _budget_chars(model)):
        reply = client.complete(model, system, chunk)
        if not reply or reply.startswith("("):
            # client.complete reports unreachable models as "(local model
            # unreachable: ...)". Treating that as "no memory found" would be
            # the silent degradation this project keeps getting bitten by.
            raise ExtractionUnavailable(reply or "the model returned nothing")
        out += parse_contract(reply, cls_name, platform=session.platform,
                              session_title=session.title)
    return out


def extract(sessions: list[Session], cls_name: str, model: Model,
            on_progress=None) -> list[Proposal]:
    """Extract one class across many sessions.

    One class per run, deliberately. Asking for six classes in one pass
    reintroduces exactly the guessing that §3.5 removes by having the user
    choose -- and the choice is what makes the type trustworthy downstream.
    """
    if model.provider == "stub":
        raise ExtractionUnavailable(
            "no model is reachable, and extraction is the one part of PERCH "
            "that cannot be stubbed -- reading a transcript and deciding what "
            "is worth keeping IS the work. Start Ollama (`ollama run "
            "qwen2.5:3b`) or set PERCH_API_BASE and PERCH_API_KEY."
        )

    proposals: list[Proposal] = []
    for n, session in enumerate(sessions, 1):
        if on_progress:
            on_progress(n, len(sessions), session.title)
        proposals += extract_session(session, cls_name, model)
    return proposals
