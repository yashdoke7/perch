"""PERCH prototype entry point.

    python -m app                 run the agent (hotkeys live)
    python -m app seed            write the demo memory set
    python -m app ask "..."       one request, headless -- the pipeline with no UI
    python -m app prompts         write the six extraction prompts to files
    python -m app import <path>   parse a platform export and propose memory
    python -m app memory          what is stored, by class
    python -m app rebuild         rebuild the index from the files
    python -m app hotkeys         probe which key combos are free on this machine
    python -m app models          which routes this machine can reach
    python -m app eval [e2 e5 ...] run the Part X experiments that can run here
    python -m app dedupe [--apply] find and merge duplicate memory items
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
        note = f"(screenshot: {shot.width}x{shot.height}px)"
        # The PATH goes to the panel now, not just a description of it. The
        # picture used to be captured, saved, and then represented to the
        # model as a filename it had no way to open.
        panel = Panel(pipeline, note, "screenshot", host, master=root,
                      image_path=str(shot.path))
        print(f"[trigger] screenshot {shot.width}x{shot.height} -> {shot.path.name}")

    else:
        panel = Panel(pipeline, "", "none", host, master=root)
        print(f"[trigger] plain      ({(time.perf_counter() - started) * 1000:.0f} ms to panel)")

    panel.show()
    return panel


# ------------------------------------------------------------- subcommands

def cmd_ask(argv: list[str]) -> None:
    """Headless. The whole pipeline, no window -- this is what tests drive.

        python -m app ask [--route local|cloud|auto] [--private] "question"
    """
    config.ensure_dirs()

    route = None
    private = False
    words: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--route" and i + 1 < len(argv):
            route = argv[i + 1].lower()
            i += 2
            continue
        if arg.startswith("--route="):
            route = arg.split("=", 1)[1].lower()
        elif arg == "--private":
            private = True
        else:
            words.append(arg)
        i += 1

    if route and route not in ("local", "cloud", "auto"):
        print(f"unknown route {route!r} — use local, cloud or auto")
        return

    question = " ".join(words) or "who am I?"
    pipeline = Pipeline(MemoryStore())
    response = pipeline.run(Request(question=question, prefer_route=route,
                                    private_toggle=private))
    print("\n".join(response.trace.lines()))
    print("\n--- answer ---")
    print(response.answer)


def cmd_models() -> None:
    """What this machine can actually route to, right now.

    §7.2 promises the user chooses the route. That promise needs somewhere to
    look before it means anything -- otherwise "switching is one click" is a
    click into an unknown set.
    """
    models = registry.available()
    print("routes available here:\n")
    for m in models:
        where = "local" if m.local else "cloud"
        caps = ", ".join(filter(None, [
            "tools" if m.tools else "", "vision" if m.vision else ""])) or "chat only"
        note = "  (fallback — no real model reachable)" if m.provider == "stub" else ""
        print(f"  {m.key:<7} {m.model_id:<22} {where:<6} "
              f"{m.context_window:>7} tok  {caps}{note}")

    chosen = registry.select(private=False)
    private = registry.select(private=True)
    print(f"\n  default route   {config.DEFAULT_ROUTE!r} -> {chosen.label()}")
    print(f"  private route   always local -> {private.label()}")
    print("\nOverride per request:  python -m app ask --route local \"...\"")
    print("Or set PERCH_ROUTE=local|cloud|auto for the default.")
    if not config.API_BASE or not config.API_KEY:
        print("\nNo cloud route configured. Set PERCH_API_BASE and PERCH_API_KEY "
              "to add one.")


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


def cmd_eval(argv: list[str]) -> None:
    """Part X, run. Prints all seven experiments including the ones that did
    not run, because an evaluation is defined as much by what it did not
    measure as by what it did."""
    config.ensure_dirs()
    from .eval import harness
    results = harness.run([a for a in argv if not a.startswith("-")] or None)
    print(harness.report(results))


def cmd_dedupe(argv: list[str]) -> None:
    """Clean up duplicates that got past the write-path merge.

    Dry-run unless --apply, because this deletes memory files and the files
    are the truth: there is no undo.
    """
    apply = "--apply" in argv
    store = MemoryStore()
    groups = store.dedupe(apply=False)
    if not groups:
        print(f"no duplicates among {store.count()} items")
        return

    total = sum(len(d) for _, d in groups)
    print(f"{len(groups)} duplicate group(s), {total} item(s) would be removed "
          f"from {store.count()}:\n")
    for keeper_id, dupe_ids in groups:
        keeper = store.get(keeper_id)
        print(f"  keep   [{keeper.cls}] {keeper.title}  (uses={keeper.uses})")
        for dupe_id in dupe_ids:
            dupe = store.get(dupe_id)
            if dupe:
                print(f"  merge    {dupe.id}  (uses={dupe.uses})")
        print()

    if not apply:
        print("Dry run - nothing was changed. Re-run with --apply to merge.")
        return

    store.dedupe(apply=True)
    print(f"merged. {store.count()} items remain.")


def cmd_rebuild() -> None:
    store = MemoryStore()
    print(f"reindexed {store.rebuild()} items from {store.root}")


def _make_stdout_unbreakable() -> None:
    """Stop a printed character from being able to kill a command.

    Windows still defaults the console to cp1252, and Python's default error
    handler on stdout is strict -- so a single character outside that codepage
    raises UnicodeEncodeError from print() and takes the command down. That is
    not hypothetical: `import --dry-run` crashed exactly here, after a
    successful extraction, at the moment it had proposals to display. The
    model's own output is user text from arbitrary conversations, so it can
    contain anything at all; no amount of care in our own format strings makes
    this safe.

    UTF-8 where the console supports it, replacement characters where it does
    not, and never an exception either way.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass          # a redirected or exotic stream; nothing to do


def main() -> None:
    _make_stdout_unbreakable()
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
    elif cmd == "models":
        cmd_models()
    elif cmd == "eval":
        cmd_eval(rest)
    elif cmd == "dedupe":
        cmd_dedupe(rest)
    elif cmd == "ablate":
        from .ablate import run
        run()
    elif cmd == "hotkeys":
        cmd_hotkeys()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
