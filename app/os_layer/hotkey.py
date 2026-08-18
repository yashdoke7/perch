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
    """Registers chords and calls back on a background thread.

    RegisterHotKey must be called from the same thread that pumps its
    messages, so it happens inside _loop() on the background thread --
    which means the caller of bind() cannot know synchronously whether
    registration actually succeeded. That gap used to be hidden: the old
    bind() returned nothing, callers collected a list of Nones, and
    "if not all(ok)" was always true regardless of what actually happened,
    so it printed a warning on every run whether or not anything was wrong.
    start() now blocks briefly on an Event and returns the real per-binding
    result, keyed by the label passed to bind(), so a caller can report
    exactly which chord failed -- which matters a lot in practice: a failed
    registration doesn't error, it just lets the keystroke fall straight
    through to whatever window has focus, silently.
    """

    def __init__(self) -> None:
        # value: (candidate (mods,vk) pairs in priority order, label, callback)
        self._bindings: dict[int, tuple[list[tuple[int, int]], str, Callable[[], None]]] = {}
        self._next_id = 1
        self._thread: threading.Thread | None = None
        self._running = False
        self.results: dict[str, bool] = {}
        # Which candidate actually won, per label -- may differ from the
        # first one requested, since fallbacks are tried in order. None if
        # every candidate was already owned by something else.
        self.assigned: dict[str, tuple[int, int] | None] = {}
        self._ready = threading.Event()

    def bind(self, modifiers: int, vk: int, callback: Callable[[], None],
             label: str = "", fallbacks: list[tuple[int, int]] | None = None) -> int:
        """Register a chord, with optional fallback (mods, vk) pairs tried in
        order if the primary one is already owned. Call before start().
        Returns the internal id."""
        hotkey_id = self._next_id
        self._next_id += 1
        candidates = [(modifiers, vk), *(fallbacks or [])]
        self._bindings[hotkey_id] = (candidates, label or f"hotkey-{hotkey_id}", callback)
        return hotkey_id

    def start(self, wait_for_registration: bool = True, timeout: float = 2.0) -> dict[str, bool]:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="perch-hotkeys")
        self._thread.start()
        if wait_for_registration:
            self._ready.wait(timeout)
        return dict(self.results)

    def stop(self) -> None:
        self._running = False

    def dispatch(self, hotkey_id: int) -> bool:
        """Fire the callback for a hotkey id. Split out of the message loop so
        it can be tested without synthesising real WM_HOTKEY messages.

        This exists because the loop previously indexed the binding tuple by
        position to reach the callback; when the tuple gained a fallback list
        and changed shape, that index silently went out of range and the
        IndexError was swallowed by the catch-all below -- the hotkey
        registered, Windows delivered it, and nothing happened. Unpacking by
        name makes that class of bug impossible to reintroduce.
        """
        binding = self._bindings.get(hotkey_id)
        if binding is None:
            return False
        _candidates, label, callback = binding
        try:
            callback()
            return True
        except Exception as exc:  # never kill the listener
            print(f"[hotkey] handler error in {label!r}: {exc}")
            return False

    def _loop(self) -> None:
        registered: list[int] = []
        for hotkey_id, (candidates, label, _) in self._bindings.items():
            won: tuple[int, int] | None = None
            for mods, vk in candidates:
                if user32.RegisterHotKey(None, hotkey_id, mods | MOD_NOREPEAT, vk):
                    won = (mods, vk)
                    registered.append(hotkey_id)
                    break

            self.results[label] = won is not None
            self.assigned[label] = won

            if won is None:
                # Almost always means another application already owns every
                # candidate chord (a browser extension, PowerToys, a second
                # PERCH instance). Windows does not error on this -- the
                # keystroke just falls through to whatever has focus instead.
                print(f"[hotkey] {label!r}: none of its {len(candidates)} candidate "
                     "combo(s) could be registered -- every one is already owned by "
                     "another application. Set its PERCH_HOTKEY_* environment "
                     "variable to something else.")
            elif won != candidates[0]:
                print(f"[hotkey] {label!r}: primary combo was already taken; "
                     "fell back to an alternate (see the trigger list below).")
        self._ready.set()

        msg = wintypes.MSG()
        try:
            while self._running:
                # PeekMessage rather than GetMessage so stop() is honoured promptly.
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == WM_HOTKEY:
                        self.dispatch(msg.wParam)
                else:
                    ctypes.windll.kernel32.Sleep(10)
        finally:
            for hotkey_id in registered:
                user32.UnregisterHotKey(None, hotkey_id)
