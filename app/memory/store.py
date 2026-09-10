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
import threading
from pathlib import Path

from .. import config
from . import classes, embed
from .schema import MemoryItem

DUPLICATE_AT = 0.92

# Set once, so the warning below is loud but not a per-query spam.
_warned_stale = False

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
        # The panel runs the pipeline on a worker thread so the UI stays
        # responsive (panel.py's _ask -> threading.Thread), which means this
        # connection is used from a different thread than the one that
        # created it. check_same_thread=False lifts sqlite3's own guard;
        # the RLock below is what actually makes that safe, since sqlite3
        # connections still are not safe for concurrent use across threads.
        # RLock (not Lock) because methods call each other -- add() calls
        # count() and _write() while already holding it.
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._lock:
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

        with self._lock:
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
        """Caller holds the lock. Not called directly from outside this class."""
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
        with self._lock:
            row = self.db.execute("SELECT path FROM items WHERE id=?", (item_id,)).fetchone()
            if not row:
                return False
            Path(row[0]).unlink(missing_ok=True)
            self.db.execute("DELETE FROM items WHERE id=?", (item_id,))
            self.db.commit()
            return True

    def touch(self, item_id: str) -> None:
        with self._lock:
            self.db.execute("UPDATE items SET uses = uses + 1 WHERE id=?", (item_id,))
            self.db.commit()

    def _evict_oldest(self, cls_name: str) -> None:
        """Caller holds the lock."""
        row = self.db.execute(
            "SELECT id FROM items WHERE class=? ORDER BY uses ASC, updated ASC LIMIT 1",
            (cls_name,),
        ).fetchone()
        if row:
            self.forget(row[0])

    # ------------------------------------------------------------------- read

    def get(self, item_id: str) -> MemoryItem | None:
        with self._lock:
            row = self.db.execute("SELECT path FROM items WHERE id=?", (item_id,)).fetchone()
        if not row:
            return None
        p = Path(row[0])
        if not p.exists():
            return None
        return MemoryItem.from_markdown(p.read_text(encoding="utf-8"))

    def count(self, cls_name: str | None = None) -> int:
        with self._lock:
            if cls_name:
                q = "SELECT COUNT(*) FROM items WHERE class=?"
                return self.db.execute(q, (cls_name,)).fetchone()[0]
            return self.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    def counts(self) -> dict[str, int]:
        with self._lock:
            rows = self.db.execute("SELECT class, COUNT(*) FROM items GROUP BY class").fetchall()
        return {c: n for c, n in rows}

    def index_health(self, live_dim: int | None = None) -> dict:
        """Which stored vectors the LIVE embedding backend can still compare against.

        The index stores whatever the backend produced at write time --
        nomic-embed-text gives 768 dimensions, the hashed fallback gives 512.
        embed.cosine() returns 0.0 when the lengths differ, so a row written
        by a different backend does not merely score badly, it scores exactly
        zero and can never be retrieved. That looks identical, from the
        outside, to "nothing was relevant" -- and the admission gate then
        correctly abstains on memory that is sitting right there.

        Measured on the development store: 9 of 18 items were written by
        Ollama and 9 by the fallback, so half the memory was invisible with
        no indication anywhere that it existed. Hence this method, and the
        loud warning in candidates().
        """
        live = live_dim if live_dim is not None else len(embed.embed("x"))
        with self._lock:
            rows = self.db.execute("SELECT vector FROM items").fetchall()
        dims: dict[int, int] = {}
        for (vec_json,) in rows:
            d = len(json.loads(vec_json))
            dims[d] = dims.get(d, 0) + 1
        return {
            "live_dim": live,
            "backend": embed.backend(),
            "dims": dims,
            "total": len(rows),
            "stale": sum(n for d, n in dims.items() if d != live),
        }

    def _warn_stale(self, n: int, total: int) -> None:
        """Loud, once. A stale index is a config error, not a retrieval result."""
        global _warned_stale
        if _warned_stale or not n:
            return
        _warned_stale = True
        print(f"  !! STALE INDEX -- {n} of {total} memory items were embedded by a "
              f"different backend")
        print(f"     than the one running now ({embed.backend()}). Vectors of "
              "different lengths cannot be")
        print("     compared, so those items score 0.0 and are UNRETRIEVABLE -- "
              "which is indistinguishable")
        print("     from having no relevant memory at all. Fix it with:  "
              "python -m app rebuild")

    def candidates(self, eligible: list[str], vector: list[float], per_class: int):
        """Over-fetch per eligible class.

        Per class, not globally: a global top-N lets one dense class crowd the
        others out before the ranker ever sees them, which silently defeats the
        multi-class routing the SOP case depends on.
        """
        out: list[tuple[MemoryItem, float]] = []
        stale = 0
        seen = 0
        for cls_name in eligible:
            with self._lock:
                rows = self.db.execute(
                    "SELECT id, vector, path FROM items WHERE class=?", (cls_name,)
                ).fetchall()
            scored = []
            for item_id, vec_json, path in rows:
                stored = json.loads(vec_json)
                seen += 1
                if len(stored) != len(vector):
                    # Not scored as 0.0 and quietly ranked last -- counted, so
                    # the user is told the item exists but cannot be reached.
                    stale += 1
                    continue
                # Calibrated relevance, not raw cosine -- see embed.relevance.
                # This is the score the ranker and admission gate see.
                sim = embed.relevance(embed.cosine(vector, stored))
                scored.append((sim, item_id, path))
            scored.sort(reverse=True)
            for sim, item_id, path in scored[:per_class]:
                p = Path(path)
                if not p.exists():
                    continue
                item = MemoryItem.from_markdown(p.read_text(encoding="utf-8"))
                if item:
                    out.append((item, sim))
        self._warn_stale(stale, seen)
        return out

    def _nearest_in_class(self, cls_name: str, vector: list[float]) -> tuple[str, float] | None:
        """Caller holds the lock.

        Rows written by a different backend are SKIPPED rather than scored at
        0.0. Scoring them zero is how the development store ended up with the
        same identity item stored twice: `seed` was run once under Ollama and
        once under the fallback, the cross-dimension cosine came back 0.0, the
        0.92 merge threshold was never reached, and a near-identical duplicate
        was created that then competed with its own twin at retrieval time.
        Skipping makes the miss explicit -- the caller still creates a new
        item, but candidates() is now the thing that says why.
        """
        rows = self.db.execute(
            "SELECT id, vector FROM items WHERE class=?", (cls_name,)
        ).fetchall()
        best: tuple[str, float] | None = None
        for item_id, vec_json in rows:
            stored = json.loads(vec_json)
            if len(stored) != len(vector):
                continue
            sim = embed.cosine(vector, stored)
            if best is None or sim > best[1]:
                best = (item_id, sim)
        return best

    # ------------------------------------------------------------ browse/edit

    def list_items(self, cls_name: str | None = None) -> list[MemoryItem]:
        """Every item, read from its file -- the files are the truth, the index
        only says where they are."""
        with self._lock:
            if cls_name:
                rows = self.db.execute(
                    "SELECT path FROM items WHERE class=? ORDER BY updated DESC",
                    (cls_name,)).fetchall()
            else:
                rows = self.db.execute(
                    "SELECT path FROM items ORDER BY class, updated DESC").fetchall()
        out: list[MemoryItem] = []
        for (path,) in rows:
            p = Path(path)
            if p.exists():
                item = MemoryItem.from_markdown(p.read_text(encoding="utf-8"))
                if item:
                    out.append(item)
        return out

    def path_of(self, item_id: str) -> Path | None:
        with self._lock:
            row = self.db.execute("SELECT path FROM items WHERE id=?", (item_id,)).fetchone()
        return Path(row[0]) if row else None

    def update(self, item: MemoryItem) -> MemoryItem:
        """Save an edited item in place.

        Never merges. add() merges near-duplicates because a restated fact
        should not accumulate; an explicit edit is the user overriding the
        store, and folding it into some other item would be the store
        overruling the user. If the class changed the file moves with it, and
        sensitivity follows the new class -- the class IS the privacy
        boundary, so an item cannot keep "normal" sensitivity after being
        moved into Health.
        """
        import datetime as _dt
        cls = classes.get(item.cls)
        if cls is None:
            raise ValueError(f"unknown class {item.cls!r}")
        item.sensitivity = "private" if cls.private else "normal"
        item.updated = _dt.date.today().isoformat()
        vector = embed.embed(item.indexed_text)
        with self._lock:
            row = self.db.execute("SELECT path FROM items WHERE id=?", (item.id,)).fetchone()
            if row and Path(row[0]) != item.path_in(self.root):
                Path(row[0]).unlink(missing_ok=True)
            self._write(item, vector)
        return item

    # ---------------------------------------------------------------- dedupe

    def find_duplicates(self, threshold: float = DUPLICATE_AT) -> list[tuple[str, list[str]]]:
        """Groups of near-identical items in the same class: (keeper, [dupes]).

        add() already prevents duplicates on the write path (§3.4 rule 3), so
        this exists to clean up what got past it. The stale-index bug is how
        they got there: a cross-dimension cosine is 0.0, which never reaches
        the 0.92 merge threshold, so re-seeding under a different embedding
        backend created a second copy of every item -- and the twins then
        competed with each other at retrieval time, each halving the other's
        apparent distinctiveness.

        The keeper is the most-used item, then the oldest: use count is
        evidence the user has actually relied on that copy.
        """
        groups: list[tuple[str, list[str]]] = []
        with self._lock:
            rows = self.db.execute(
                "SELECT id, class, vector, uses, updated FROM items"
            ).fetchall()

        by_class: dict[str, list] = {}
        for item_id, cls_name, vec_json, uses, updated in rows:
            by_class.setdefault(cls_name, []).append(
                (item_id, json.loads(vec_json), uses, updated))

        for members in by_class.values():
            claimed: set[str] = set()
            for i, (id_a, vec_a, uses_a, upd_a) in enumerate(members):
                if id_a in claimed:
                    continue
                twins = []
                for id_b, vec_b, uses_b, upd_b in members[i + 1:]:
                    if id_b in claimed or len(vec_a) != len(vec_b):
                        continue
                    if embed.cosine(vec_a, vec_b) >= threshold:
                        twins.append((id_b, uses_b, upd_b))
                if not twins:
                    continue
                family = [(id_a, uses_a, upd_a)] + twins
                family.sort(key=lambda r: (-r[1], r[2]))    # most used, then oldest
                keeper = family[0][0]
                dupes = [r[0] for r in family[1:]]
                claimed.update([keeper] + dupes)
                groups.append((keeper, dupes))
        return groups

    def dedupe(self, apply: bool = False,
               threshold: float = DUPLICATE_AT) -> list[tuple[str, list[str]]]:
        """Merge duplicate groups into their keeper. Dry-run unless apply=True.

        Dry-run by default because this DELETES memory files, and the files
        are the truth -- there is no undo. The caller is expected to show the
        user what would go before anything does.
        """
        groups = self.find_duplicates(threshold)
        if not apply:
            return groups

        for keeper_id, dupe_ids in groups:
            keeper = self.get(keeper_id)
            if keeper is None:
                continue
            for dupe_id in dupe_ids:
                dupe = self.get(dupe_id)
                if dupe is not None:
                    # Union rather than discard: a twin may carry a tag the
                    # keeper lacks, and losing it would be a silent downgrade.
                    keeper.tags = sorted(set(keeper.tags) | set(dupe.tags))
                    keeper.entities = sorted(set(keeper.entities) | set(dupe.entities))
                    keeper.uses = max(keeper.uses, dupe.uses)
                self.forget(dupe_id)
            with self._lock:
                self._write(keeper, embed.embed(keeper.indexed_text))
        return groups

    # ---------------------------------------------------------------- rebuild

    def rebuild(self) -> int:
        """Reconstruct the index from the files. The files are the truth."""
        with self._lock:
            self.db.execute("DELETE FROM items")
            self.db.commit()
            n = 0
            for path in sorted(self.root.rglob("*.md")):
                item = MemoryItem.from_markdown(path.read_text(encoding="utf-8"))
                if item:
                    self._write(item, embed.embed(item.indexed_text))
                    n += 1
            return n
