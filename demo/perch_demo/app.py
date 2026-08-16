"""
Wires the OS layer together (§3, Phase 0).

Three triggers, one panel, one paste-back path:

    Ctrl+Shift+Space   capture the selection and ask about it       (T1 + T2)
    Ctrl+Shift+S       drag a region, capture it, ask about it      (T1 + T3)
    Ctrl+Shift+P       ask with no selection at all                 (T1)

Everything runs from a background hotkey thread. The panel is created on the
main thread because tkinter requires it.
"""

from __future__ import annotations

import queue
import time
from pathlib import Path

from . import capture, hotkey, model, panel, screenshot, winapi

VK_SPACE = 0x20
VK_S = 0x53
VK_P = 0x50

SHOT_DIR = Path(__file__).resolve().parent.parent / ".captures"

_requests: "queue.Queue[str]" = queue.Queue()


def _log(kind: str, host: winapi.WindowInfo | None, extra: str = "") -> None:
    where = f"{host.title[:50]!r} at ({host.left},{host.top}) {host.width}x{host.height}" if host else "unknown"
    print(f"[trigger] {kind:<10} host={where} {extra}")


def _on_selection() -> None:
    _requests.put("selection")


def _on_screenshot() -> None:
    _requests.put("screenshot")


def _on_plain() -> None:
    _requests.put("plain")


def _handle(kind: str) -> None:
    # Snapshot the host window FIRST. Once our panel appears, GetForegroundWindow
    # returns us, and we would lose the thing we are supposed to be helping with.
    host = winapi.foreground_window()

    if kind == "selection":
        sel = capture.capture_selection(host)
        _log("selection", host, f"method={sel.method} chars={len(sel.text)}")
        p = panel.Panel(sel.text, sel.method, sel.source_title, host, model.ask)
        p.show()

    elif kind == "screenshot":
        _log("screenshot", host)
        shot = screenshot.grab_region(SHOT_DIR)
        if shot is None:
            print("[trigger] screenshot cancelled")
            return
        print(f"[trigger] screenshot   saved={shot.path} {shot.width}x{shot.height}")
        note = f"(screenshot captured: {shot.width}x{shot.height}px at {shot.path.name})"
        p = panel.Panel(note, "none", host.title if host else "(unknown)", host, model.ask)
        p.show()

    else:
        _log("plain", host)
        p = panel.Panel("", "none", host.title if host else "(unknown)", host, model.ask)
        p.show()


def main() -> None:
    listener = hotkey.HotkeyListener()
    mods = hotkey.MOD_CONTROL | hotkey.MOD_SHIFT
    listener.bind(mods, VK_SPACE, _on_selection)
    listener.bind(mods, VK_S, _on_screenshot)
    listener.bind(mods, VK_P, _on_plain)
    listener.start()

    print("PERCH — OS layer demo")
    print("  Ctrl+Shift+Space   ask about the current selection")
    print("  Ctrl+Shift+S       screenshot a region and ask about it")
    print("  Ctrl+Shift+P       ask with nothing selected")
    print("  Ctrl+C here        quit\n")
    print("Try it: select this line in Notepad, then press Ctrl+Shift+Space.\n")

    try:
        while True:
            try:
                kind = _requests.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                _handle(kind)
            except Exception as exc:
                print(f"[error] {kind}: {exc}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        listener.stop()
