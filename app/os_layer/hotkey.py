"""
T1 — global hotkeys (§3.1).

RegisterHotKey is the documented Win32 way to claim a system-wide chord. The
registering thread must pump messages, so we run a dedicated thread with its own
message loop and hand events back to the app via a callback.

In Tauri this whole file collapses to tauri-plugin-global-shortcut.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

user32 = ctypes.windll.user32


class HotkeyListener:
    """Registers chords and calls back on a background thread."""

    def __init__(self) -> None:
        self._bindings: dict[int, tuple[int, int, Callable[[], None]]] = {}
        self._next_id = 1
        self._thread: threading.Thread | None = None
        self._running = False

    def bind(self, modifiers: int, vk: int, callback: Callable[[], None]) -> None:
        """Register a chord. Call before start()."""
        self._bindings[self._next_id] = (modifiers | MOD_NOREPEAT, vk, callback)
        self._next_id += 1

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="perch-hotkeys")
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _loop(self) -> None:
        registered: list[int] = []
        for hotkey_id, (mods, vk, _) in self._bindings.items():
            if user32.RegisterHotKey(None, hotkey_id, mods, vk):
                registered.append(hotkey_id)
            else:
                # Almost always means another application already owns the chord.
                print(f"[hotkey] could not register id={hotkey_id} (already taken?)")

        msg = wintypes.MSG()
        try:
            while self._running:
                # PeekMessage rather than GetMessage so stop() is honoured promptly.
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == WM_HOTKEY:
                        binding = self._bindings.get(msg.wParam)
                        if binding:
                            try:
                                binding[2]()
                            except Exception as exc:  # never kill the listener
                                print(f"[hotkey] handler error: {exc}")
                else:
                    ctypes.windll.kernel32.Sleep(10)
        finally:
            for hotkey_id in registered:
                user32.UnregisterHotKey(None, hotkey_id)
