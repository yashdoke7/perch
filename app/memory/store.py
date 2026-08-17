"""The memory store: Markdown files are the truth, SQLite is the index.

Write path enforces the three rules from architecture §3.4, which is how memory
growth stays bounded:

    1. nothing is stored silently from ordinary chat
    2. imports are proposed and reviewed, never auto-committed
    3. near-duplicates MERGE rather than accumulate (cosine > 0.92, same class)

Delete index.sqlite3 at any time; rebuild() reconstructs it from the files.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .. import config
from . import classes, embed
from .schema import MemoryItem

DUPLICATE_AT = 0.92

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id        TEXT PRIMARY KEY,
    class     TEXT NOT NULL,
    title     TEXT NOT NULL,
    tags      TEXT NOT NULL,
    entities  TEXT NOT NULL,
    updated   TEXT NOT NULL,
    uses      INTEGER NOT NULL DEFAULT 0,
    vector    TEXT NOT NULL,
    path      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS items_class ON items(class);
"""


class MemoryStore:
    def __init__(self, root: Path | None = None, db: Path | None = None) -> None:
        self.root = root or config.MEMORY_DIR
        self.db_path = db or config.INDEX_DB
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.db_path)
        self.db.executescript(SCHEMA)
        self.db.commit()

    # ------------------------------------------------------------------ write

    def add(self, item: MemoryItem, allow_merge: bool = True) -> tuple[MemoryItem, str]:
        """Returns (stored_item, 'created' | 'merged').

        Merging is the scale rule: a fact restated in a later session updates the
        item that already holds it instead of creating a second, near-identical
        copy that will then compete with itself at retrieval time.
        """
        vector = embed.embed(item.indexed_text)

        if allow_merge:
            twin = self._nearest_in_class(item.cls, vector)
            if twin and twin[1] >= DUPLICATE_AT:
                existing = self.get(twin[0])
                if existing:
                    existing.body = item.body
                    existing.tags = sorted(set(existing.tags) | set(item.tags))
                    existing.entities = sorted(set(existing.entities) | set(item.entities))
                    existing.updated = item.updated
                    self._write(existing, embed.embed(existing.indexed_text))
                    return existing, "merged"

        cls = classes.get(item.cls)
        if cls and self.count(item.cls) >= cls.cap:
            self._evict_oldest(item.cls)

        if cls and cls.private:
            item.sensitivity = "private"

        self._write(item, vector)
        return item, "created"

    def _write(self, item: MemoryItem, vector: list[float]) -> None:
        path = item.path_in(self.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item.to_markdown(), encoding="utf-8")
        self.db.execute(
            "INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?,?)",
            (
                item.id, item.cls, item.title,
                json.dumps(item.tags), json.dumps(item.entities),
                item.updated, item.uses, json.dumps(vector), str(path),
            ),
        )
        self.db.commit()

    def forget(self, item_id: str) -> bool:
        row = self.db.execute("SELECT path FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return False
        Path(row[0]).unlink(missing_ok=True)
        self.db.execute("DELETE FROM items WHERE id=?", (item_id,))
        self.db.commit()
        return True

    def touch(self, item_id: str) -> None:
        self.db.execute("UPDATE items SET uses = uses + 1 WHERE id=?", (item_id,))
        self.db.commit()

    def _evict_oldest(self, cls_name: str) -> None:
        row = self.db.execute(
            "SELECT id FROM items WHERE class=? ORDER BY uses ASC, updated ASC LIMIT 1",
            (cls_name,),
        ).fetchone()
        if row:
            self.forget(row[0])

    # ------------------------------------------------------------------- read

    def get(self, item_id: str) -> MemoryItem | None:
        row = self.db.execute("SELECT path FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return None
        p = Path(row[0])
        if not p.exists():
            return None
        return MemoryItem.from_markdown(p.read_text(encoding="utf-8"))

    def count(self, cls_name: str | None = None) -> int:
        if cls_name:
            q = "SELECT COUNT(*) FROM items WHERE class=?"
            return self.db.execute(q, (cls_name,)).fetchone()[0]
        return self.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    def counts(self) -> dict[str, int]:
        rows = self.db.execute("SELECT class, COUNT(*) FROM items GROUP BY class").fetchall()
        return {c: n for c, n in rows}

    def candidates(self, eligible: list[str], vector: list[float], per_class: int):
        """Over-fetch per eligible class.

        Per class, not globally: a global top-N lets one dense class crowd the
        others out before the ranker ever sees them, which silently defeats the
        multi-class routing the SOP case depends on.
        """
        out: list[tuple[MemoryItem, float]] = []
        for cls_name in eligible:
            rows = self.db.execute(
                "SELECT id, vector, path FROM items WHERE class=?", (cls_name,)
            ).fetchall()
            scored = []
            for item_id, vec_json, path in rows:
                sim = embed.cosine(vector, json.loads(vec_json))
                scored.append((sim, item_id, path))
            scored.sort(reverse=True)
            for sim, item_id, path in scored[:per_class]:
                p = Path(path)
                if not p.exists():
                    continue
                item = MemoryItem.from_markdown(p.read_text(encoding="utf-8"))
                if item:
                    out.append((item, sim))
        return out

    def _nearest_in_class(self, cls_name: str, vector: list[float]) -> tuple[str, float] | None:
        rows = self.db.execute(
            "SELECT id, vector FROM items WHERE class=?", (cls_name,)
        ).fetchall()
        best: tuple[str, float] | None = None
        for item_id, vec_json in rows:
            sim = embed.cosine(vector, json.loads(vec_json))
            if best is None or sim > best[1]:
                best = (item_id, sim)
        return best

    # ---------------------------------------------------------------- rebuild

    def rebuild(self) -> int:
        """Reconstruct the index from the files. The files are the truth."""
        self.db.execute("DELETE FROM items")
        self.db.commit()
        n = 0
        for path in sorted(self.root.rglob("*.md")):
            item = MemoryItem.from_markdown(path.read_text(encoding="utf-8"))
            if item:
                self._write(item, embed.embed(item.indexed_text))
                n += 1
        return n
