"""
Edit in place (§3.3) — putting the answer back where the user was working.

This is the capability that separates PERCH from a chat window, and the whole
trick is that we do not need per-application integration:

    in every Windows text field, pasting while text is selected REPLACES it.

So "replace this sentence" is: restore focus to the host window, put the answer
on the clipboard, send Ctrl+V, restore the user's clipboard. No Office add-in,
no VS Code extension, no browser extension — it works in whatever was in front.
"""

from __future__ import annotations

import time
from typing import Literal

from . import winapi

Action = Literal["replace", "insert_after", "copy_only"]


def deliver(answer: str, hwnd: int | None, action: Action) -> tuple[bool, str]:
    """Return (succeeded, human-readable explanation of what happened)."""

    if action == "copy_only" or hwnd is None:
        ok = winapi.set_clipboard_text(answer)
        return ok, "Copied to clipboard." if ok else "Could not access the clipboard."

    original = winapi.get_clipboard_text()

    payload = answer if action == "replace" else "\n" + answer
    if not winapi.set_clipboard_text(payload):
        return False, "Could not access the clipboard."

    if not winapi.refocus(hwnd):
        # Windows blocked the focus change. Do NOT paste — it would land in the
        # wrong window. Degrade to copy-only and say so.
        if original is not None:
            time.sleep(0.05)
        return False, "Windows blocked the focus change. Answer left on the clipboard."

    time.sleep(0.08)  # let focus actually settle before the keystroke
    winapi.send_paste()
    time.sleep(0.12)  # let the host app consume the paste before we take it back

    if original is not None:
        winapi.set_clipboard_text(original)

    verb = "Replaced the selection." if action == "replace" else "Inserted below the selection."
    return True, verb
