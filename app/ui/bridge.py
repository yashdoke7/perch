"""The app's API: everything the web UI may ask the Python core to do.

pywebview exposes every public method of this object to JavaScript as
window.pywebview.api.<name>(...), each call running on its own thread and
returning a Promise. That shapes three rules:

  * EVERY attribute is underscore-prefixed. pywebview walks the public
    attributes of a js_api object and exposes them, so a public `store` would
    hand the page the whole memory store.
  * Long work never blocks a call. ask(), import and eval start a thread and
    return an id at once; progress flows back through poll().
  * Python never reaches into the page. The page polls. A worker thread
    calling into the UI is how the tkinter panel froze mid-demo (OS primer
    §5.2a); with polling the only thing crossing threads is a queue, so that
    whole class of bug cannot happen here.

The one exception is Shell.nudge(), a fire-and-forget run_js asking the page
to poll now rather than in 250 ms. If it fails, the next poll catches up.
"""

from __future__ import annotations

import os
import queue
import threading
import uuid
from dataclasses import asdict
from pathlib import Path

from .. import config
from .. import settings as settings_mod
from ..core import privacy
from ..core.pipeline import Pipeline, Request
from ..memory import classes as mc
from ..memory import embed
from ..memory.schema import MemoryItem
from ..memory.sessions import Session, SessionStore
from ..memory.store import MemoryStore
from ..models import registry
from ..tools import registry as toolreg

ROUTES = ("auto", "local", "cloud")

# How many exchanges carry into the next question. The packer truncates oldest
# first anyway (§4.5 fill order, step 3), so this bounds what it is ever asked
# to consider -- an unbounded list would grow a long session's prompt until
# memory started being evicted to pay for chat nobody referred to again.
MAX_HISTORY_TURNS = 6

# How long a tool-permission request waits before silence counts as "no".
CONFIRM_TIMEOUT_S = 120.0

TOOL_WARNINGS = {
    "file_write": "This writes a file on your computer, replacing it if it exists.",
    "run_python": "This runs Python code with your permissions. It is not sandboxed.",
    "memory_write": "This saves a new memory about you.",
}


def _item(item: MemoryItem) -> dict:
    return {"id": item.id, "cls": item.cls, "title": item.title, "body": item.body,
            "tags": list(item.tags), "entities": list(item.entities),
            "created": item.created, "updated": item.updated, "uses": item.uses,
            "source": item.source_kind, "platform": item.source_platform,
            "ref": item.source_ref, "confidence": item.confidence,
            "private": mc.is_private_class(item.cls)}


def _result(r) -> dict:
    return {"name": r.name, "title": r.title, "claim": r.claim, "ran": r.ran,
            "reason": r.reason, "verdict": r.verdict, "lines": list(r.lines)}


class Api:
    def __init__(self, shell=None, pipeline: Pipeline | None = None,
                 sessions: SessionStore | None = None) -> None:
        self._shell = shell
        self._pipeline = pipeline or Pipeline(MemoryStore())
        self._store = self._pipeline.store
        self._sessions = sessions or SessionStore(cap=int(settings_mod.load()["session_cap"]))
        self._events: "queue.Queue[dict]" = queue.Queue()
        self._lock = threading.Lock()
        self._busy = False
        self._context: dict = {}
        self._host = None
        self._session: Session | None = None
        self._last_answer = ""
        self._confirms: dict[str, dict] = {}
        self._proposals: list = []

    # ============================================================ internal

    def _emit(self, kind: str, **data) -> None:
        data["type"] = kind
        self._events.put(data)

    def _nudge(self) -> None:
        if self._shell is not None:
            self._shell.nudge()

    def _open(self, context: dict, host=None) -> None:
        """A summon: new context, new conversation. Called by the shell."""
        self._deny_all()
        self._host = host
        self._context = dict(context)
        self._session = None
        self._last_answer = ""
        self._emit("open", context=dict(self._context))
        self._nudge()

    def _deny_all(self) -> None:
        """Every pending permission request becomes a refusal. Hiding the
        window must never leave a tool waiting for a yes that could arrive
        later from a panel the user thinks is closed."""
        for slot in list(self._confirms.values()):
            slot["ok"] = False
            slot["ev"].set()
        self._confirms.clear()

    def _new_session(self) -> Session:
        c = self._context
        return Session(source_app=c.get("app_label") or c.get("source_app", ""),
                       capture=c.get("method", ""),
                       selection=(c.get("selection") or "")[:4000],
                       image=c.get("image", ""))

    def _record(self, question: str, response) -> None:
        values = settings_mod.load()
        if self._session is None:
            self._session = self._new_session()
        trace = response.trace
        self._session.private = self._session.private or bool(trace.private)
        self._session.add("user", question)
        self._session.add("assistant", response.answer, model=trace.model,
                          private=bool(trace.private), abstained=bool(trace.abstained),
                          admitted=[s.item.title for s in trace.admitted])
        keep = values["keep_sessions"] and (not self._session.private
                                            or values["keep_private_sessions"])
        if keep:
            self._sessions.save(self._session)
        elif self._session.private:
            # It may have been written before the conversation turned private.
            self._sessions.delete(self._session.id)

    def _confirm(self, rid: str, name: str, args: dict) -> bool:
        """The approval callback the tool loop calls, on the worker thread.

        Every path that is not an explicit yes returns False: a timeout, a
        hidden window, an unknown id. The one direction this must never fail
        in is "allowed by accident".
        """
        cid = uuid.uuid4().hex[:10]
        slot = {"ev": threading.Event(), "ok": False}
        self._confirms[cid] = slot
        self._emit("confirm", rid=rid, cid=cid, tool=name,
                   call=toolreg.describe_call(name, args),
                   warning=TOOL_WARNINGS.get(name, "This changes something outside PERCH."))
        self._nudge()
        if not slot["ev"].wait(CONFIRM_TIMEOUT_S):
            self._confirms.pop(cid, None)
            self._emit("confirm_timeout", cid=cid)
            return False
        self._confirms.pop(cid, None)
        return bool(slot["ok"])

    def _run(self, rid: str, req: Request, question: str) -> None:
        try:
            response = self._pipeline.run(
                req,
                on_stage=lambda name, detail: self._emit("stage", rid=rid, name=name,
                                                         detail=detail),
                on_token=lambda text: self._emit("token", rid=rid, text=text),
                on_confirm=lambda name, args: self._confirm(rid, name, args))
            self._last_answer = response.answer
            try:
                self._record(question, response)
            except Exception as exc:                          # noqa: BLE001
                print(f"[sessions] could not save: {exc}")
            self._emit("done", rid=rid, answer=response.answer,
                       trace=response.trace.to_dict())
        except Exception as exc:                              # noqa: BLE001
            self._emit("error", rid=rid, message=f"{type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                self._busy = False
            self._nudge()

    def _status(self) -> dict:
        model = registry.select(private=False)
        semantic = embed.is_semantic()
        health = self._store.index_health()
        warnings = []
        if model.provider == "stub":
            warnings.append({"level": "error",
                             "text": "No model is reachable, so answers are stubbed.",
                             "fix": "Start Ollama (ollama serve), then restart PERCH."})
        if not semantic:
            warnings.append({"level": "warn",
                             "text": "Fallback embeddings: memory recall is badly degraded.",
                             "fix": "Start Ollama with nomic-embed-text and restart PERCH."})
        if health["stale"]:
            warnings.append({"level": "warn",
                             "text": f"{health['stale']} memories were indexed by another "
                                     "embedder and cannot be recalled.",
                             "fix": "Rebuild the index.", "action": "rebuild"})
        return {
            "model": {"label": model.label(), "id": model.model_id, "local": model.local,
                      "stub": model.provider == "stub", "vision": model.vision,
                      "tools": model.tools, "window": model.context_window},
            "embeddings": embed.backend(), "semantic": semantic,
            "memory": self._store.count(), "counts": self._store.counts(),
            "warnings": warnings,
        }

    def _models(self) -> list[dict]:
        registry.forget_probe()
        return [{"key": m.key, "id": m.model_id, "local": m.local, "window": m.context_window,
                 "tools": m.tools, "vision": m.vision, "stub": m.provider == "stub",
                 "label": m.label()} for m in registry.available()]

    def _proposal(self, index: int, p) -> dict:
        item = p.item
        return {"index": index, "cls": item.cls, "title": item.title, "body": item.body,
                "tags": list(item.tags), "entities": list(item.entities),
                "platform": item.source_platform, "session": p.session_title,
                "confidence": item.confidence, "warnings": list(p.warnings)}

    # ============================================================ lifecycle

    def boot(self) -> dict:
        from ..os_layer import ocr
        return {
            "version": config.APP_VERSION,
            "routes": list(ROUTES),
            "classes": [{"name": n, "holds": mc.CLASSES[n].holds,
                         "floor": mc.CLASSES[n].floor, "private": mc.CLASSES[n].private,
                         "cap": mc.CLASSES[n].cap, "schema": list(mc.CLASSES[n].schema)}
                        for n in mc.ORDER],
            "settings": settings_mod.load(),
            "status": self._status(),
            "context": dict(self._context),
            "hotkeys": self._shell.hotkeys() if self._shell else {},
            "ocr": ocr.available(),
        }

    def status(self) -> dict:
        return self._status()

    def poll(self) -> list:
        out: list[dict] = []
        while True:
            try:
                ev = self._events.get_nowait()
            except queue.Empty:
                break
            # Coalesce a burst of tokens into one event: fewer round trips,
            # same text.
            if (ev["type"] == "token" and out and out[-1]["type"] == "token"
                    and out[-1]["rid"] == ev["rid"]):
                out[-1]["text"] += ev["text"]
            else:
                out.append(ev)
        return out

    def context(self) -> dict:
        return dict(self._context)

    # ============================================================ asking

    def ask(self, question: str, private: bool = False, route: str = "auto") -> dict:
        question = (question or "").strip()
        if not question:
            return {"ok": False, "error": "empty"}
        with self._lock:
            if self._busy:
                return {"ok": False, "error": "busy"}
            self._busy = True
        rid = uuid.uuid4().hex[:8]
        c = self._context
        history = self._session.history()[-MAX_HISTORY_TURNS * 2:] if self._session else []
        req = Request(question=question, selection=c.get("selection", ""),
                      source_app=c.get("source_app", ""),
                      source_title=c.get("source_title", ""),
                      private_toggle=bool(private),
                      prefer_route=None if route not in ("local", "cloud") else route,
                      image_path=c.get("image", ""), history=history)
        threading.Thread(target=self._run, args=(rid, req, question), daemon=True,
                         name="perch-ask").start()
        return {"ok": True, "rid": rid}

    def confirm(self, cid: str, ok: bool) -> bool:
        slot = self._confirms.get(cid)
        if slot is None:
            return False
        slot["ok"] = bool(ok)
        slot["ev"].set()
        return True

    def new_chat(self) -> bool:
        self._deny_all()
        self._session = None
        self._last_answer = ""
        return True

    def deliver(self, action: str) -> dict:
        from ..os_layer import inject
        if action not in ("replace", "insert_after", "copy_only"):
            return {"ok": False, "message": "Unknown action."}
        answer = self._last_answer
        if not answer:
            return {"ok": False, "message": "Ask something first."}
        host = self._host
        if action == "copy_only" or host is None:
            ok, message = inject.deliver(answer, None, "copy_only")
            return {"ok": ok, "message": message, "hidden": False}
        if self._shell is not None:
            self._shell.hide()

        def work() -> None:
            ok, message = inject.deliver(answer, host.hwnd, action)   # type: ignore[arg-type]
            print(f"[deliver] {'ok' if ok else 'failed'}: {message}")
            self._emit("delivered", ok=ok, message=message)

        threading.Thread(target=work, daemon=True, name="perch-deliver").start()
        return {"ok": True, "message": "", "hidden": True}

    def copy_text(self, text: str) -> bool:
        from ..os_layer import winapi
        return winapi.set_clipboard_text(text or "")

    # ============================================================ window

    def hide(self) -> bool:
        self._deny_all()
        if self._shell is not None:
            self._shell.hide()
        return True

    def set_mode(self, mode: str) -> bool:
        if self._shell is not None:
            self._shell.set_mode(mode)
        return True

    def grip(self, dx: float, dy: float, phase: str) -> bool:
        if self._shell is not None:
            self._shell.grip(dx, dy, phase)
        return True

    def accent(self, private: bool) -> bool:
        if self._shell is not None:
            self._shell.set_border(bool(private))
        return True

    def quit(self) -> bool:
        if self._shell is not None:
            self._shell.quit()
        return True

    def open_folder(self, which: str) -> bool:
        target = {"home": config.ROOT, "memory": config.MEMORY_DIR,
                  "sessions": self._sessions.root, "captures": config.CAPTURES,
                  "eval": config.ROOT / "eval"}.get(which)
        if target is None:
            return False
        Path(target).mkdir(parents=True, exist_ok=True)
        os.startfile(str(target))                             # noqa: S606
        return True

    # ============================================================ sessions

    def sessions(self, query: str = "") -> list:
        return self._sessions.list(query or "")

    def session(self, sid: str) -> dict | None:
        s = self._sessions.get(sid)
        return s.to_dict() if s else None

    def session_delete(self, sid: str) -> bool:
        if self._session is not None and self._session.id == sid:
            self._session = None
        return self._sessions.delete(sid)

    def sessions_clear(self) -> int:
        self._session = None
        return self._sessions.clear()

    def session_resume(self, sid: str) -> dict:
        s = self._sessions.get(sid)
        if s is None:
            return {"ok": False}
        self._deny_all()
        self._session = s
        self._host = None            # an old window is no place to paste into
        image = s.image if s.image and Path(s.image).exists() else ""
        self._context = {"kind": "resumed", "selection": s.selection,
                         "method": s.capture or "none", "source_title": "",
                         "source_app": s.source_app, "app_label": s.source_app,
                         "image": image, "thumb": "", "has_host": False, "resumed": s.id}
        self._last_answer = next((t.text for t in reversed(s.turns)
                                  if t.role == "assistant"), "")
        return {"ok": True, "context": dict(self._context),
                "turns": [asdict(t) for t in s.turns]}

    # ============================================================ memory

    def memory_overview(self) -> dict:
        counts = self._store.counts()
        return {"total": sum(counts.values()), "counts": counts,
                "folder": str(config.MEMORY_DIR), "embeddings": embed.backend(),
                "semantic": embed.is_semantic(),
                "stale": self._store.index_health()["stale"]}

    def memory_list(self, cls: str = "", query: str = "") -> list:
        items = self._store.list_items(cls or None)
        q = (query or "").strip().lower()
        if q:
            items = [i for i in items if q in i.title.lower() or q in i.body.lower()
                     or any(q in t.lower() for t in i.tags)]
        return [_item(i) for i in items]

    def memory_save(self, data: dict) -> dict:
        data = data or {}
        cls = (data.get("cls") or "").strip().lower()
        title = (data.get("title") or "").strip()
        body = (data.get("body") or "").strip()
        if cls not in mc.CLASSES:
            return {"ok": False, "error": "Choose a class."}
        if not title or not body:
            return {"ok": False, "error": "A memory needs a title and some text."}
        tags = [t.strip().lower() for t in (data.get("tags") or []) if str(t).strip()][:8]
        existing = self._store.get(data["id"]) if data.get("id") else None
        if existing is not None:
            existing.cls, existing.title, existing.body, existing.tags = cls, title, body, tags
            stored = self._store.update(existing)
            return {"ok": True, "how": "updated", "item": _item(stored)}
        stored, how = self._store.add(MemoryItem(cls=cls, title=title, body=body, tags=tags,
                                                 source_kind="manual"))
        return {"ok": True, "how": how, "item": _item(stored)}

    def memory_delete(self, item_id: str) -> bool:
        return self._store.forget(item_id)

    def memory_open(self, item_id: str) -> bool:
        path = self._store.path_of(item_id)
        if path is None or not path.exists():
            return False
        os.startfile(str(path))                               # noqa: S606
        return True

    def gate_preview(self, question: str) -> dict:
        q = (question or "").strip()
        if not q:
            return {"ok": False}
        trace = self._pipeline.preview(q)
        return {"ok": True, "trace": trace.to_dict(), "semantic": embed.is_semantic()}

    def dedupe(self, apply: bool = False) -> dict:
        groups = self._store.find_duplicates()
        described = []
        for keeper, dupes in groups:
            k = self._store.get(keeper)
            described.append({"keep": k.title if k else keeper, "cls": k.cls if k else "",
                              "remove": len(dupes)})
        if apply and groups:
            self._store.dedupe(apply=True)
        return {"groups": described, "applied": bool(apply and groups),
                "total": self._store.count()}

    def seed_demo(self) -> dict:
        from ..seed import SEED
        created = merged = 0
        for row in SEED:
            _, how = self._store.add(MemoryItem(source_kind="manual", **row))
            created += how == "created"
            merged += how == "merged"
        return {"created": created, "merged": merged, "total": self._store.count()}

    def rebuild_index(self) -> dict:
        n = self._store.rebuild()
        return {"ok": True, "items": n, "health": self._store.index_health()}

    # ============================================================ import

    def import_pick(self) -> dict:
        path = self._shell.pick_file() if self._shell is not None else ""
        if not path:
            return {"ok": False, "cancelled": True}
        return self.import_inspect(path)

    def import_inspect(self, path: str) -> dict:
        from ..ingest import exports
        try:
            sessions = exports.load(path)
        except exports.ExportError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:                              # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        platforms: dict[str, int] = {}
        for s in sessions:
            platforms[s.platform] = platforms.get(s.platform, 0) + 1
        return {"ok": True, "path": path, "name": Path(path).name, "count": len(sessions),
                "platforms": platforms, "chars": sum(s.chars for s in sessions),
                "sessions": [{"title": s.title, "platform": s.platform,
                              "turns": len(s.turns), "chars": s.chars}
                             for s in sessions[:40]]}

    def import_extract(self, path: str, cls: str) -> dict:
        if cls not in mc.CLASSES:
            return {"ok": False, "error": "unknown class"}
        job = uuid.uuid4().hex[:8]

        def work() -> None:
            from ..ingest import exports, extract, review
            try:
                sessions = exports.load(path)
                # The class is the privacy boundary: a Health or Personal import
                # never reaches a cloud model, even when one is configured.
                model = registry.select(private=mc.is_private_class(cls))
                self._emit("job", job=job, kind="import", state="start",
                           n=0, total=len(sessions), label=model.label())
                proposals = extract.extract(
                    sessions, cls, model,
                    on_progress=lambda n, total, title: self._emit(
                        "job", job=job, kind="import", state="progress",
                        n=n, total=total, label=title))
                self._proposals = proposals
                self._emit("job", job=job, kind="import", state="done",
                           proposals=[self._proposal(i, p) for i, p in enumerate(proposals)],
                           uncalibrated=review.uncalibrated(proposals), model=model.label())
            except extract.ExtractionUnavailable as exc:
                self._emit("job", job=job, kind="import", state="error", message=str(exc))
            except Exception as exc:                          # noqa: BLE001
                self._emit("job", job=job, kind="import", state="error",
                           message=f"{type(exc).__name__}: {exc}")
            self._nudge()

        threading.Thread(target=work, daemon=True, name="perch-import").start()
        return {"ok": True, "job": job}

    def import_commit(self, decisions: list) -> dict:
        from ..ingest import review
        if not self._proposals:
            return {"ok": False, "error": "Nothing to save."}
        by_index = {int(d.get("index", -1)): d for d in (decisions or [])}
        for i, p in enumerate(self._proposals):
            d = by_index.get(i, {})
            p.accepted = bool(d.get("keep"))
            title = (d.get("title") or "").strip()
            if title:
                p.item.title = title[:120]
        summary = review.commit(self._proposals, self._store)
        self._proposals = []
        return {"ok": True, "summary": asdict(summary), "total": self._store.count()}

    # ============================================================ evaluation

    def eval_run(self, names: list) -> dict:
        job = uuid.uuid4().hex[:8]
        wanted = [str(n).lower() for n in (names or [])]

        def work() -> None:
            from ..eval import e1_overpersonalisation, harness
            results = []
            for i, name in enumerate(wanted, 1):
                self._emit("job", job=job, kind="eval", state="progress", n=i,
                           total=len(wanted), label=name.upper())
                try:
                    if name == "e1":
                        r = e1_overpersonalisation.run(progress=lambda d, t, label: self._emit(
                            "job", job=job, kind="eval", state="progress", n=d, total=t,
                            label=f"E1 · {d}/{t} · {label[:60]}"))
                    else:
                        r = harness.run([name])[0]
                    results.append(_result(r))
                except Exception as exc:                      # noqa: BLE001
                    results.append({"name": name.upper(), "title": "(crashed)", "claim": "",
                                    "ran": False, "reason": f"{type(exc).__name__}: {exc}",
                                    "verdict": "", "lines": []})
                self._emit("job", job=job, kind="eval", state="result", result=results[-1])
                self._nudge()
            self._emit("job", job=job, kind="eval", state="done", results=results)
            self._nudge()

        threading.Thread(target=work, daemon=True, name="perch-eval").start()
        return {"ok": True, "job": job}

    def eval_saved(self) -> dict:
        from ..eval import e1_overpersonalisation
        return _result(e1_overpersonalisation.last_result())

    # ============================================================ settings

    def settings_get(self) -> dict:
        from ..os_layer import ocr
        return {"values": settings_mod.load(), "locked": settings_mod.locked(),
                "login": settings_mod.launches_at_login(), "rules": privacy.load_rules(),
                "models": self._models(),
                "hotkeys": self._shell.hotkeys() if self._shell else {},
                "paths": {"home": str(config.ROOT), "memory": str(config.MEMORY_DIR),
                          "sessions": str(self._sessions.root)},
                "ocr": ocr.available(), "embeddings": embed.backend(),
                "version": config.APP_VERSION}

    def settings_save(self, changes: dict) -> dict:
        values = settings_mod.save(changes or {})
        self._sessions.cap = int(values["session_cap"])
        return {"ok": True, "values": values, "login": settings_mod.launches_at_login()}

    def rules_save(self, rules: dict) -> dict:
        clean = {key: [str(x).strip() for x in (rules or {}).get(key, []) if str(x).strip()]
                 for key in ("apps", "titles", "folders")}
        privacy.save_rules(clean)
        return {"ok": True, "rules": clean}
