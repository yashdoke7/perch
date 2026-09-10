"""Episodic memory: the conversations themselves (architecture §3.2, system stores).

This is NOT typed memory, and the difference is load-bearing.

    typed memory (store.py)   facts about you, one per file, classed, gated,
                              retrieved into prompts, written only when you say
    episodic (this module)    what was asked and answered, kept so you can
                              reopen a thread; NEVER retrieved into a prompt,
                              NEVER promoted to typed memory on its own

§3.4 rule 1 -- "nothing is stored silently from ordinary chat" -- is about the
first kind. Keeping a transcript you can see, search and delete is not the same
as quietly learning from it, and conflating the two is how assistants end up
"remembering" things the user never agreed to.

Two privacy defaults, both deliberate:

  * a conversation that ran in PRIVATE mode is not written unless the user
    turns on keep_private_sessions. The request never left the machine; the
    transcript should not outlive the window either, unless asked.
  * the store is capped (oldest first), because an unbounded history is a
    liability nobody reviews.

Format: one JSON file per session. Readable, deletable, portable -- the same
reasons the typed store is Markdown.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .. import config

DEFAULT_CAP = 200


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


@dataclass
class Turn:
    role: str                      # "user" | "assistant"
    text: str
    at: str = field(default_factory=_now)
    meta: dict = field(default_factory=dict)


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created: str = field(default_factory=_now)
    updated: str = field(default_factory=_now)
    title: str = ""
    source_app: str = ""
    capture: str = ""              # "uia" | "clipboard" | "screenshot" | "none"
    selection: str = ""
    image: str = ""
    private: bool = False
    turns: list[Turn] = field(default_factory=list)

    def add(self, role: str, text: str, **meta) -> None:
        self.turns.append(Turn(role=role, text=text, meta=meta))
        self.updated = _now()
        if not self.title and role == "user":
            self.title = text.strip().splitlines()[0][:80] if text.strip() else ""

    def history(self) -> list[tuple[str, str]]:
        return [(t.role, t.text) for t in self.turns]

    def summary(self) -> dict:
        last = self.turns[-1].text if self.turns else ""
        return {
            "id": self.id, "title": self.title or "(untitled)",
            "created": self.created, "updated": self.updated,
            "source_app": self.source_app, "capture": self.capture,
            "private": self.private, "turns": len(self.turns),
            "preview": last.strip().replace("\n", " ")[:140],
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        turns = [Turn(**t) for t in data.pop("turns", [])]
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(turns=turns, **known)


class SessionStore:
    def __init__(self, root: Path | None = None, cap: int = DEFAULT_CAP) -> None:
        self.root = root or (config.ROOT / "sessions")
        self.root.mkdir(parents=True, exist_ok=True)
        self.cap = cap
        self._lock = threading.Lock()

    def _path(self, sid: str) -> Path:
        safe = "".join(c for c in sid if c.isalnum())
        return self.root / f"{safe}.json"

    def save(self, session: Session) -> None:
        if not session.turns:
            return                  # an opened-and-dismissed panel is not a conversation
        with self._lock:
            self._path(session.id).write_text(
                json.dumps(session.to_dict(), ensure_ascii=False, indent=1),
                encoding="utf-8")
            self._enforce_cap()

    def get(self, sid: str) -> Session | None:
        p = self._path(sid)
        if not p.exists():
            return None
        try:
            return Session.from_dict(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None

    def delete(self, sid: str) -> bool:
        p = self._path(sid)
        with self._lock:
            if p.exists():
                p.unlink()
                return True
        return False

    def list(self, query: str = "", limit: int = 200) -> list[dict]:
        q = query.strip().lower()
        out = []
        for p in self.root.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if q:
                haystack = " ".join([data.get("title", ""), data.get("source_app", "")]
                                    + [t.get("text", "") for t in data.get("turns", [])])
                if q not in haystack.lower():
                    continue
            try:
                out.append(Session.from_dict(data).summary())
            except TypeError:
                continue
        out.sort(key=lambda s: s["updated"], reverse=True)
        return out[:limit]

    def clear(self) -> int:
        n = 0
        with self._lock:
            for p in self.root.glob("*.json"):
                p.unlink(missing_ok=True)
                n += 1
        return n

    def _enforce_cap(self) -> None:
        """Caller holds the lock. Oldest by last update goes first."""
        files = sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime)
        for p in files[: max(0, len(files) - self.cap)]:
            p.unlink(missing_ok=True)
