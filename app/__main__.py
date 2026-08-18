"""PERCH prototype entry point.

    python -m app                 run the agent (hotkeys live)
    python -m app seed            write the demo memory set
    python -m app ask "..."       one request, headless -- the pipeline with no UI
    python -m app prompts         write the six extraction prompts to files
    python -m app import <path>   parse a platform export and propose memory
    python -m app memory          what is stored, by class
    python -m app rebuild         rebuild the index from the files
"""

from __future__ import annotations

import queue
import sys
import time

from . import config
from .core.pipeline import Pipeline, Request
from .memory.store import MemoryStore
from .os_layer import capture, hotkey, screenshot, winapi
from .ui.panel import Panel

_requests: "queue.Queue[str]" = queue.Queue()


# ------------------------------------------------------------------ the agent

def run_agent() -> None:
    config.ensure_dirs()
    pipeline = Pipeline(MemoryStore())

    listener = hotkey.HotkeyListener()
    triggers = [
        ("selection", config.HOTKEY_SELECTION, config.HOTKEY_SELECTION_FALLBACKS,
         "ask about the current selection", lambda: _requests.put("selection")),
        ("screenshot", config.HOTKEY_SCREENSHOT, config.HOTKEY_SCREENSHOT_FALLBACKS,
         "screenshot a region and ask", lambda: _requests.put("screenshot")),
        ("plain", config.HOTKEY_PLAIN, config.HOTKEY_PLAIN_FALLBACKS,
         "ask with nothing selected", lambda: _requests.put("plain")),
    ]
    for label, (mods, vk), fallbacks, _desc, callback in triggers:
        listener.bind(mods, vk, callback, label=label, fallbacks=fallbacks)
    listener.start()  # blocks briefly; listener.assigned then holds the REAL, live combo

    counts = pipeline.store.counts()
    total = sum(counts.values())
    print("PERCH — prototype")
    print(f"  memory      {total} items  {counts or '(empty — run: python -m app seed)'}")
    print(f"  embeddings  {__import__('app.memory.embed', fromlist=['x']).backend()}\n")

    any_failed = False
    for label, combo, _fallbacks, desc, _cb in triggers:
        won = listener.assigned.get(label)
        if won is not None:
            live = config.describe_combo(*won)
            note = "" if won == combo else f"  (fell back from {config.describe_combo(*combo)})"
            print(f"  {live:<22} {desc}{note}")
        else:
            any_failed = True
            print(f"  {config.describe_combo(*combo):<22} {desc}   "
                 "! NOT REGISTERED -- every candidate combo is already owned "
                 "by another app; keystrokes reach IT instead")
    print("  Ctrl+C here            quit\n")
    if any_failed:
        print("  Set PERCH_HOTKEY_SELECTION / _SCREENSHOT / _PLAIN to a different combo, "
             "e.g. PERCH_HOTKEY_SELECTION=\"ctrl+alt+shift+j\", and restart.\n")

    try:
        while True:
            try:
                kind = _requests.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                _handle(pipeline, kind)
            except Exception as exc:                       # noqa: BLE001
                print(f"[error] {kind}: {exc}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        listener.stop()


def _handle(pipeline: Pipeline, kind: str) -> None:
    # Snapshot the host BEFORE any of our own UI exists, or GetForegroundWindow
    # returns us. See PERCH_OS_PRIMER.md §1.1.
    host = winapi.foreground_window()

    if kind == "selection":
        sel = capture.capture_selection(host)
        print(f"[trigger] selection  host={host.title[:40]!r} "
              f"method={sel.method} chars={len(sel.text)}")
        Panel(pipeline, sel.text, sel.method, host).show()

    elif kind == "screenshot":
        shot = screenshot.grab_region(config.CAPTURES)
        if shot is None:
            print("[trigger] screenshot cancelled")
            return
        note = f"(screenshot: {shot.width}x{shot.height}px saved to {shot.path.name})"
        Panel(pipeline, note, "none", host).show()

    else:
        Panel(pipeline, "", "none", host).show()


# ------------------------------------------------------------- subcommands

def cmd_ask(argv: list[str]) -> None:
    """Headless. The whole pipeline, no window -- this is what tests drive."""
    config.ensure_dirs()
    question = " ".join(argv) or "who am I?"
    pipeline = Pipeline(MemoryStore())
    response = pipeline.run(Request(question=question))
    print("\n".join(response.trace.lines()))
    print("\n--- answer ---")
    print(response.answer)


def cmd_memory() -> None:
    store = MemoryStore()
    counts = store.counts()
    if not counts:
        print("memory is empty — run: python -m app seed")
        return
    for cls_name, n in sorted(counts.items()):
        print(f"{cls_name:<10} {n:>4}")
    print(f"{'total':<10} {sum(counts.values()):>4}")


def cmd_prompts() -> None:
    from .ingest import prompts
    target = config.ROOT / "prompts"
    for path in prompts.write_prompt_files(target):
        print(f"wrote {path}")


def cmd_import(argv: list[str]) -> None:
    from .ingest import exports
    if not argv:
        print("usage: python -m app import <export.zip|conversations.json>")
        return
    try:
        sessions = exports.load(argv[0])
    except exports.ExportError as exc:
        print(f"import failed: {exc}")
        return
    print(exports.summarise(sessions))
    for s in sessions[:10]:
        print(f"  [{s.platform}] {s.title[:60]}  ({len(s.turns)} turns, {s.chars:,} chars)")
    print("\nNothing was stored. Extraction and review are Phase 2 —")
    print("run `python -m app prompts` for the six extraction prompts you can use now.")


def cmd_rebuild() -> None:
    store = MemoryStore()
    print(f"reindexed {store.rebuild()} items from {store.root}")


def main() -> None:
    argv = sys.argv[1:]
    if not argv:
        return run_agent()
    cmd, rest = argv[0], argv[1:]
    if cmd == "seed":
        from .seed import seed
        seed()
    elif cmd == "ask":
        cmd_ask(rest)
    elif cmd == "memory":
        cmd_memory()
    elif cmd == "prompts":
        cmd_prompts()
    elif cmd == "import":
        cmd_import(rest)
    elif cmd == "rebuild":
        cmd_rebuild()
    elif cmd == "ablate":
        from .ablate import run
        run()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
