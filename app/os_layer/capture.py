"""
T2 — read the user's current selection from any Windows application.

Two paths, exactly as described in the architecture (§3.1):

  Path A  UI Automation      clean, no side effects, but coverage varies by app
  Path B  clipboard round-trip   universal, restores the user's clipboard afterwards

We try A, fall back to B, and record which one worked. That per-application
coverage table is a deliverable in its own right — nobody publishes one.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

from . import winapi

Method = Literal["uia", "clipboard", "none"]

try:
    import uiautomation as auto

    _UIA_AVAILABLE = True
except Exception:  # pragma: no cover - depends on the machine
    _UIA_AVAILABLE = False


@dataclass
class Selection:
    """What the user had selected, plus where it came from.

    `source_app` and `source_title` are what Private-mode source rules match on
    (§4.4) — we never inspect the text to decide whether it is sensitive.
    """

    text: str
    method: Method
    source_app: str
    source_title: str

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


def _via_uia() -> str | None:
    """Path A: ask the focused control for its selected text range."""
    if not _UIA_AVAILABLE:
        return None
    try:
        element = auto.GetFocusedControl()
        if element is None:
            return None
        pattern = element.GetTextPattern()
        if pattern is None:
            return None
        ranges = pattern.GetSelection()
        if not ranges:
            return None
        parts = []
        for i in range(ranges.Length):
            text = ranges.GetElement(i).GetText(-1)
            if text:
                parts.append(text)
        joined = "".join(parts)
        return joined or None
    except Exception:
        # Any COM hiccup means "this app does not cooperate" — fall back quietly.
        return None


def _via_clipboard() -> str | None:
    """Path B: save the clipboard, press Ctrl+C, read it, put the old one back.

    The restore step is not optional. Silently destroying whatever the user had
    copied is exactly the kind of small betrayal that gets an app uninstalled.
    """
    original = winapi.get_clipboard_text()
    sentinel = f"__perch_probe_{time.time_ns()}__"
    winapi.set_clipboard_text(sentinel)

    winapi.send_copy()

    captured = None
    for _ in range(25):  # ~250ms; the host app needs a moment to service Ctrl+C
        time.sleep(0.01)
        current = winapi.get_clipboard_text()
        if current is not None and current != sentinel:
            captured = current
            break

    # Restore whatever the user actually had, even if the capture failed.
    if original is not None:
        winapi.set_clipboard_text(original)
    else:
        winapi.set_clipboard_text("")

    return captured


def capture_selection(window: winapi.WindowInfo | None) -> Selection:
    source_title = window.title if window else "(unknown)"
    source_app = source_title.split(" - ")[-1] if window else "(unknown)"

    text = _via_uia()
    if text:
        return Selection(text, "uia", source_app, source_title)

    text = _via_clipboard()
    if text:
        return Selection(text, "clipboard", source_app, source_title)

    return Selection("", "none", source_app, source_title)
