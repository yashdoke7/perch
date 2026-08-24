"""PERCH prototype entry point.

    python -m app                 run the agent (hotkeys live)
    python -m app seed            write the demo memory set
    python -m app ask "..."       one request, headless -- the pipeline with no UI
    python -m app prompts         write the six extraction prompts to files
    python -m app import <path>   parse a platform export and propose memory
    python -m app memory          what is stored, by class
    python -m app rebuild         rebuild the index from the files
    python -m app hotkeys         probe which key combos are free on this machine
"""

from __future__ import annotations

import queue
import sys
import time
import tkinter as tk

from . import config
from .core.pipeline import Pipeline, Request
from .memory.store import MemoryStore
from .models import registry
from .os_layer import capture, hotkey, screenshot, winapi
from .ui.panel import Panel

_requests: "queue.Queue[str]" = queue.Queue()

# How often the root's loop drains the hotkey queue. 25 ms is imperceptible
# to a user and costs nothing measurable, and it bounds the worst-case delay
# between pressing the chord and the capture starting.
POLL_MS = 25


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
    from .memory import embed as _embed
    print(f"  embeddings  {_embed.backend()}")
    if not _embed.is_semantic():
        # Loud, because the degradation is otherwise invisible: retrieval still
        # "works", it just stops being able to match anything that does not
        # share literal words, and the admission gate inherits that.
        print("  !! FALLBACK EMBEDDINGS -- retrieval quality is badly degraded.")
        print("     The hashed stand-in matches shared vocabulary only, so it")
        print("     cannot relate 'rewrite this formally' to a note about your")
        print("     writing style. Start Ollama and `ollama pull nomic-embed-text`,")
        print("     then run `python -m app rebuild`.")
    # A stale index is the worse of the two failures, because it is completely
    # invisible: the affected items do not rank badly, they cannot be compared
    # at all. Reported at startup so it is fixed before it is mistaken for the
    # gate being too strict.
    health = pipeline.store.index_health()
    if health["stale"]:
        print(f"  !! STALE INDEX -- {health['stale']} of {health['total']} items were "
              "embedded by another backend")
        print(f"     (dimensions found: {health['dims']}, live: {health['live_dim']}). "
              "They are UNRETRIEVABLE")
        print("     until you run:  python -m app rebuild")
    print()

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

    # ONE root, ONE mainloop, for the life of the process.
    #
    # The old loop called Panel.show(), which ran its own mainloop() and
    # blocked here until that panel closed -- so a hotkey pressed while a
    # panel was open could not be serviced at all. It sat in the queue, and
    # the whole backlog then fired at once on dismissal. Now the root's loop
    # always runs and drains the queue on a timer, so a trigger is picked up
    # within one poll interval whether or not a panel is already up.
    root = tk.Tk()
    root.withdraw()

    state: dict[str, Panel | None] = {"panel": None}

    def poll() -> None:
        try:
            kind = _requests.get_nowait()
        except queue.Empty:
            root.after(POLL_MS, poll)
            return

        # Coalesce a burst. Holding the chord, or pressing it repeatedly while
        # nothing appeared, should summon ONE panel -- not a queue of them.
        dropped = 0
        while True:
            try:
                _requests.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        if dropped:
            print(f"[trigger] coalesced {dropped} repeated press(es)")

        try:
            previous = state["panel"]
            if previous is not None and previous.alive:
                previous.close()      # a new trigger replaces the old panel
            state["panel"] = _handle(pipeline, kind, root)
        except Exception as exc:                           # noqa: BLE001
            print(f"[error] {kind}: {exc}")
        root.after(POLL_MS, poll)

    root.after(POLL_MS, poll)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        listener.stop()


def _handle(pipeline: Pipeline, kind: str, root: "tk.Tk") -> "Panel | None":
    # Snapshot the host BEFORE any of our own UI exists, or GetForegroundWindow
    # returns us. See PERCH_OS_PRIMER.md §1.1.
    host = winapi.foreground_window()

    started = time.perf_counter()

    if kind == "selection":
        sel = capture.capture_selection(host)
        panel = Panel(pipeline, sel.text, sel.method, host, master=root)
        print(f"[trigger] selection  host={host.title[:40]!r} "
              f"method={sel.method} chars={len(sel.text)} "
              f"({(time.perf_counter() - started) * 1000:.0f} ms to panel)")

    elif kind == "screenshot":
        shot = screenshot.grab_region(config.CAPTURES, master=root)
        if shot is None:
            print("[trigger] screenshot cancelled")
            return None
        note = f"(screenshot: {shot.width}x{shot.height}px saved to {shot.path.name})"
        panel = Panel(pipeline, note, "none", host, master=root)

    else:
        panel = Panel(pipeline, "", "none", host, master=root)
        print(f"[trigger] plain      ({(time.perf_counter() - started) * 1000:.0f} ms to panel)")

    panel.show()
    return panel


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
    """Phase 2, end to end: parse -> extract (one class) -> review -> store.

        python -m app import <export.zip> [class] [--dry-run]

    The class is an argument rather than something we infer, and that is the
    whole point: §3.5 has the user type the memory at the SOURCE, which is
    what makes the admission gate's per-class floors mean anything later.
    """
    from .ingest import exports, extract, review
    from .memory import classes as mc

    args = [a for a in argv if not a.startswith("--")]
    dry_run = "--dry-run" in argv

    if not args:
        print("usage: python -m app import <export.zip|conversations.json> "
              f"[{('|'.join(mc.ORDER))}] [--dry-run]")
        return

    config.ensure_dirs()
    try:
        sessions = exports.load(args[0])
    except exports.ExportError as exc:
        print(f"import failed: {exc}")
        return

    print(exports.summarise(sessions))
    for s in sessions[:10]:
        print(f"  [{s.platform}] {s.title[:60]}  ({len(s.turns)} turns, {s.chars:,} chars)")
    if len(sessions) > 10:
        print(f"  ... and {len(sessions) - 10} more")

    # --- which class -----------------------------------------------------
    cls_name = args[1].lower() if len(args) > 1 else ""
    if cls_name not in mc.CLASSES:
        if cls_name:
            print(f"\nunknown class {cls_name!r}")
        print(f"\nWhich class is this import? One run extracts ONE class.")
        for name in mc.ORDER:
            print(f"  {name:<10} {mc.CLASSES[name].holds}")
        try:
            cls_name = input("\nclass: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\ncancelled")
            return
        if cls_name not in mc.CLASSES:
            print(f"unknown class {cls_name!r} — nothing was imported")
            return

    # --- extract ---------------------------------------------------------
    model = registry.select(private=False)
    print(f"\nextracting {cls_name} with {model.label()}")

    def progress(n: int, total: int, title: str) -> None:
        print(f"  [{n}/{total}] {title[:60]}")

    try:
        proposals = extract.extract(sessions, cls_name, model, on_progress=progress)
    except extract.ExtractionUnavailable as exc:
        print(f"\nextraction unavailable: {exc}")
        return

    print(f"\n{len(proposals)} proposals from {len(sessions)} sessions")
    if dry_run:
        print("--dry-run: showing proposals, storing nothing\n")
        for i, p in enumerate(proposals, 1):
            print(review.render(p, i, len(proposals)))
            print()
        return

    summary = review.review(proposals, MemoryStore())
    print()
    print("\n".join(summary.lines()))


def cmd_hotkeys() -> None:
    """Probe which combos this machine will actually give us.

    Collisions are machine-specific and Windows reports them only through
    RegisterHotKey's return value, so the only reliable answer is to try.
    """
    import ctypes
    from .os_layer.hotkey import MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, MOD_SHIFT

    user32 = ctypes.windll.user32
    combos = [
        ("ctrl+alt+space", MOD_CONTROL | MOD_ALT, 0x20),
        ("ctrl+alt+shift+space", MOD_CONTROL | MOD_ALT | MOD_SHIFT, 0x20),
        ("ctrl+shift+space", MOD_CONTROL | MOD_SHIFT, 0x20),
        ("ctrl+alt+j", MOD_CONTROL | MOD_ALT, ord("J")),
        ("ctrl+alt+k", MOD_CONTROL | MOD_ALT, ord("K")),
        ("ctrl+alt+g", MOD_CONTROL | MOD_ALT, ord("G")),
        ("ctrl+alt+q", MOD_CONTROL | MOD_ALT, ord("Q")),
        ("ctrl+alt+s", MOD_CONTROL | MOD_ALT, ord("S")),
        ("ctrl+alt+p", MOD_CONTROL | MOD_ALT, ord("P")),
        ("ctrl+alt+shift+j", MOD_CONTROL | MOD_ALT | MOD_SHIFT, ord("J")),
        ("ctrl+alt+shift+k", MOD_CONTROL | MOD_ALT | MOD_SHIFT, ord("K")),
        ("ctrl+alt+shift+g", MOD_CONTROL | MOD_ALT | MOD_SHIFT, ord("G")),
    ]

    print("Probing hotkey combinations on this machine.")
    print("Close PERCH before running this, or it will report its own as taken.\n")
    free = []
    for name, mods, vk in combos:
        ok = user32.RegisterHotKey(None, 4242, mods | MOD_NOREPEAT, vk)
        if ok:
            user32.UnregisterHotKey(None, 4242)
            free.append(name)
            print(f"  {name:<24} free")
        else:
            print(f"  {name:<24} TAKEN by another application")

    if free:
        print("\nUse any of the free ones, for example:\n")
        picks = (free + free + free)[:3]
        print(f'  set PERCH_HOTKEY_SELECTION={picks[0]}')
        print(f'  set PERCH_HOTKEY_SCREENSHOT={picks[1]}')
        print(f'  set PERCH_HOTKEY_PLAIN={picks[2]}')
        print("\n  (PowerShell: $env:PERCH_HOTKEY_SELECTION=\"%s\")" % picks[0])
    else:
        print("\nNothing free in that list -- try adding Shift, or a function key.")


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
    elif cmd == "hotkeys":
        cmd_hotkeys()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
