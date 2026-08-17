"""Parsing official platform data exports (architecture §1.4).

This is the mechanism that makes the whole project work, and it is worth being
precise about why it exists:

    There is no cross-vendor memory API and there will never be one -- memory
    is the switching cost, so exposing it funds your own churn. But every
    major platform ships a DATA EXPORT, because regulators require it.

    That export is the only ToS-legitimate bridge between a vendor's memory of
    you and your own. It is a feature of the subscription you already pay for.

    ChatGPT   Settings -> Data Controls -> Export data     conversations.json
    Claude    Settings -> Privacy -> export                JSON
    Gemini    takeout.google.com -> Gemini only            JSON / HTML

Parsers are isolated per platform and FAIL LOUDLY. These formats are
undocumented and can change without notice, so a parser that silently returns
nothing is worse than one that raises -- see architecture §11.5.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Session:
    platform: str
    title: str
    created: str
    turns: list[tuple[str, str]] = field(default_factory=list)

    def as_text(self, limit: int = 24000) -> str:
        out = []
        for role, text in self.turns:
            if text.strip():
                out.append(f"{role.upper()}: {text.strip()}")
        return "\n\n".join(out)[:limit]

    @property
    def chars(self) -> int:
        return sum(len(t) for _, t in self.turns)


class ExportError(RuntimeError):
    pass


# ---------------------------------------------------------------------- entry

def load(path: str | Path) -> list[Session]:
    """Accepts the emailed .zip or an already-extracted .json."""
    p = Path(path)
    if not p.exists():
        raise ExportError(f"no such file: {p}")

    if p.suffix.lower() == ".zip":
        return _from_zip(p)
    if p.suffix.lower() == ".json":
        return _from_json(json.loads(p.read_text(encoding="utf-8", errors="replace")),
                          hint=p.name)
    raise ExportError(f"unsupported export file: {p.name} (expected .zip or .json)")


def _from_zip(p: Path) -> list[Session]:
    sessions: list[Session] = []
    with zipfile.ZipFile(p) as zf:
        names = zf.namelist()
        # ChatGPT ships a zip inside a zip.
        inner = [n for n in names if n.lower().endswith(".zip")]
        for n in inner:
            with zf.open(n) as fh:
                tmp = Path(p.parent / "._perch_inner.zip")
                tmp.write_bytes(fh.read())
                try:
                    sessions += _from_zip(tmp)
                finally:
                    tmp.unlink(missing_ok=True)

        for n in names:
            if not n.lower().endswith(".json"):
                continue
            if "conversation" not in n.lower() and "chat" not in n.lower():
                continue
            with zf.open(n) as fh:
                try:
                    data = json.loads(fh.read().decode("utf-8", "replace"))
                except json.JSONDecodeError as exc:
                    raise ExportError(f"{n} is not valid JSON: {exc}") from exc
            sessions += _from_json(data, hint=n)

    if not sessions:
        raise ExportError(
            f"{p.name} contained no recognisable conversation JSON. "
            "Expected a ChatGPT, Claude or Gemini export."
        )
    return sessions


def _from_json(data, hint: str = "") -> list[Session]:
    if isinstance(data, dict):
        for key in ("conversations", "chats", "data"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ExportError(f"{hint}: expected a list of conversations")

    out: list[Session] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        session = _chatgpt(entry) or _claude(entry) or _generic(entry)
        if session and session.turns:
            out.append(session)
    return out


# ------------------------------------------------------------------- platforms

def _chatgpt(entry: dict) -> Session | None:
    """ChatGPT stores a message GRAPH keyed by id, not a flat list."""
    mapping = entry.get("mapping")
    if not isinstance(mapping, dict):
        return None

    rows = []
    for node in mapping.values():
        msg = (node or {}).get("message")
        if not msg:
            continue
        role = (msg.get("author") or {}).get("role", "")
        if role not in ("user", "assistant"):
            continue
        parts = (msg.get("content") or {}).get("parts") or []
        text = "\n".join(p for p in parts if isinstance(p, str))
        if text.strip():
            rows.append((msg.get("create_time") or 0, role, text))

    rows.sort(key=lambda r: r[0])
    return Session(
        platform="chatgpt",
        title=entry.get("title") or "(untitled)",
        created=str(entry.get("create_time") or ""),
        turns=[(r, t) for _, r, t in rows],
    )


def _claude(entry: dict) -> Session | None:
    messages = entry.get("chat_messages")
    if not isinstance(messages, list):
        return None
    turns = []
    for m in messages:
        role = m.get("sender") or m.get("role") or ""
        role = {"human": "user", "assistant": "assistant"}.get(role, role)
        text = m.get("text") or ""
        if not text and isinstance(m.get("content"), list):
            text = "\n".join(c.get("text", "") for c in m["content"] if isinstance(c, dict))
        if text.strip() and role in ("user", "assistant"):
            turns.append((role, text))
    return Session(
        platform="claude",
        title=entry.get("name") or entry.get("title") or "(untitled)",
        created=str(entry.get("created_at") or ""),
        turns=turns,
    )


def _generic(entry: dict) -> Session | None:
    """Gemini/Takeout and anything else with a flat messages list."""
    messages = entry.get("messages") or entry.get("turns")
    if not isinstance(messages, list):
        return None
    turns = []
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = m.get("role") or m.get("author") or "user"
        text = m.get("text") or m.get("content") or ""
        if isinstance(text, list):
            text = "\n".join(str(x) for x in text)
        if str(text).strip():
            turns.append((str(role), str(text)))
    return Session(
        platform="gemini",
        title=entry.get("title") or "(untitled)",
        created=str(entry.get("create_time") or entry.get("created") or ""),
        turns=turns,
    )


def summarise(sessions: list[Session]) -> str:
    by_platform: dict[str, int] = {}
    for s in sessions:
        by_platform[s.platform] = by_platform.get(s.platform, 0) + 1
    chars = sum(s.chars for s in sessions)
    parts = ", ".join(f"{n} from {p}" for p, n in sorted(by_platform.items()))
    return f"{len(sessions)} sessions ({parts}), {chars:,} characters"
