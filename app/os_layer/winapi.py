"""
Thin wrapper over the Win32 calls PERCH's OS layer needs.

Everything here maps 1:1 onto a documented Windows API, and each one has a Rust
equivalent for when this moves into Tauri:

    GetForegroundWindow / GetWindowRect   -> windows crate (Win32::UI::WindowsAndMessaging)
    SetForegroundWindow                   -> same
    clipboard get/set                     -> arboard / clipboard-win
    keybd_event (Ctrl+C, Ctrl+V)          -> SendInput via windows crate
    RegisterHotKey                        -> tauri-plugin-global-shortcut

The point of the demo is that none of this needs a driver, a kernel hook, or a
special permission. It is the same surface screen readers have used for years.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import win32api
import win32clipboard
import win32con
import win32gui

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12          # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_C = 0x43
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002

_MODIFIERS = (VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN)


@dataclass
class WindowInfo:
    """A snapshot of whatever the user was working in when they triggered us."""

    hwnd: int
    title: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def foreground_window() -> WindowInfo | None:
    """The window the user is actually looking at.

    Captured at trigger time and held for the whole interaction: we need it to
    place the panel, and again later to paste the answer back into the right place.
    """
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return None
    try:
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    except Exception:
        return None
    return WindowInfo(
        hwnd=hwnd,
        title=win32gui.GetWindowText(hwnd) or "(untitled)",
        left=left,
        top=top,
        right=right,
        bottom=bottom,
    )


def refocus(hwnd: int) -> bool:
    """Give focus back to the host window.

    Needed before paste-back: the selection still exists in the host app, but the
    keystroke has to land there and not on our panel.
    """
    try:
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception:
        # Windows refuses SetForegroundWindow in some focus states. The caller
        # degrades to "copy only" rather than pasting into the wrong window.
        return False


def get_clipboard_text() -> str | None:
    for _ in range(10):  # the clipboard is a shared resource; brief contention is normal
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                return None
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.02)
    return None


def set_clipboard_text(text: str) -> bool:
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
                return True
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.02)
    return False


def modifiers_held() -> list[int]:
    """Which modifier keys the user is physically holding right now."""
    return [vk for vk in _MODIFIERS if win32api.GetAsyncKeyState(vk) & 0x8000]


def wait_for_modifier_release(timeout: float = 0.7) -> bool:
    """Block until the user lets go of Ctrl/Alt/Shift/Win, or give up.

    This is essential, not defensive. PERCH is summoned by a chord like
    Ctrl+Alt+J, so at the instant the callback runs the user is still
    physically holding Ctrl and Alt. Synthesising Ctrl+C on top of a held
    Alt makes the target application receive Ctrl+ALT+C, which is not copy
    in any normal app -- the clipboard never changes, capture returns
    nothing, and the model is asked to reason about a selection it never
    got. Returns True if the keys came up on their own.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not modifiers_held():
            return True
        time.sleep(0.015)
    return False


def _release_modifiers() -> None:
    """Force-release any modifier still down, so a synthetic chord is clean.

    Only used after wait_for_modifier_release() times out -- if the user is
    leaning on a key we would otherwise send a corrupted chord forever.
    """
    for vk in modifiers_held():
        win32api.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _chord(vk: int) -> None:
    """Send Ctrl+<vk> to whatever currently has focus.

    Waits for the summoning chord's own modifiers to clear first; see
    wait_for_modifier_release().
    """
    if not wait_for_modifier_release():
        _release_modifiers()
        time.sleep(0.02)

    win32api.keybd_event(VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(vk, 0, 0, 0)
    win32api.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def send_copy() -> None:
    _chord(VK_C)


def send_paste() -> None:
    _chord(VK_V)
