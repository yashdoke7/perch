"""A memory item is one Markdown file with YAML frontmatter (§3.3).

The file is the truth. The SQLite index is a derived artefact that can be
deleted and rebuilt. That ordering is deliberate: memory you cannot open and
read is memory you cannot trust, and after Recall that is not a slogan.

We hand-roll the frontmatter parser rather than depend on PyYAML -- the schema
is fixed and small, and one fewer dependency matters for a tool people are
supposed to install and keep.
"""

from __future__ import annotations

import datetime as dt
import re
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def _today() -> str:
    return dt.date.today().isoformat()


@dataclass
class MemoryItem:
    cls: str
    title: str
    body: str
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    sensitivity: str = "normal"          # normal | private
    source_kind: str = "manual"          # manual | import | live
    source_platform: str = ""            # chatgpt | claude | gemini | ""
    source_ref: str = ""
    confidence: float = 1.0
    created: str = field(default_factory=_today)
    updated: str = field(default_factory=_today)
    uses: int = 0
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")[:32]
            self.id = f"{self.cls[:3]}-{slug or 'item'}-{uuid.uuid4().hex[:6]}"

    # ------------------------------------------------------------- text views

    @property
    def indexed_text(self) -> str:
        """What the embedder sees. Title carries a lot of signal, so it repeats."""
        return f"{self.title}\n{' '.join(self.tags)}\n{self.body}"

    def rendered(self) -> str:
        """What goes into the prompt. Compact -- every character costs budget."""
        head = f"[{self.cls}] {self.title}"
        if self.tags:
            head += f"  ({', '.join(self.tags[:6])})"
        return f"{head}\n{self.body.strip()}"

    def approx_tokens(self, chars_per_token: float) -> int:
        return int(len(self.rendered()) / chars_per_token) + 1

    # -------------------------------------------------------------- file form

    def to_markdown(self) -> str:
        lines = [
            "---",
            f"id: {self.id}",
            f"class: {self.cls}",
            f"title: {self.title}",
            f"tags: [{', '.join(self.tags)}]",
            f"entities: [{', '.join(self.entities)}]",
            f"sensitivity: {self.sensitivity}",
            f"source: {{kind: {self.source_kind}, platform: {self.source_platform}, "
            f"ref: {self.source_ref}, confidence: {self.confidence}}}",
            f"created: {self.created}",
            f"updated: {self.updated}",
            f"uses: {self.uses}",
            "---",
            "",
            self.body.strip(),
            "",
        ]
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "MemoryItem | None":
        m = FM.match(text)
        if not m:
            return None
        head, body = m.group(1), m.group(2)
        fields: dict[str, str] = {}
        for line in head.splitlines():
            if ":" not in line:
                continue
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()

        def listval(key: str) -> list[str]:
            raw = fields.get(key, "").strip().strip("[]")
            return [p.strip() for p in raw.split(",") if p.strip()]

        src = fields.get("source", "")
        def srcval(key: str, default: str = "") -> str:
            m2 = re.search(rf"{key}\s*:\s*([^,}}]*)", src)
            return m2.group(1).strip() if m2 else default

        try:
            confidence = float(srcval("confidence", "1.0") or 1.0)
        except ValueError:
            confidence = 1.0

        return cls(
            id=fields.get("id", ""),
            cls=fields.get("class", "personal"),
            title=fields.get("title", "(untitled)"),
            body=body.strip(),
            tags=listval("tags"),
            entities=listval("entities"),
            sensitivity=fields.get("sensitivity", "normal"),
            source_kind=srcval("kind", "manual"),
            source_platform=srcval("platform"),
            source_ref=srcval("ref"),
            confidence=confidence,
            created=fields.get("created", _today()),
            updated=fields.get("updated", _today()),
            uses=int(fields.get("uses", "0") or 0),
        )

    def path_in(self, root: Path) -> Path:
        return root / self.cls / f"{self.id}.md"


@dataclass
class Scored:
    """A candidate with everything the gate needs to explain its own decision."""
    item: MemoryItem
    similarity: float = 0.0
    tag_overlap: float = 0.0
    entity_hit: float = 0.0
    recency: float = 0.0
    score: float = 0.0
    admitted: bool = False
    reason: str = ""

    def explain(self) -> str:
        state = "admitted" if self.admitted else "dropped"
        return f"{state}: [{self.item.cls}] {self.item.title} (score {self.score:.3f}) - {self.reason}"
