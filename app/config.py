"""Paths, tunables and environment wiring.

Everything the pipeline can be tuned by lives here, so an ablation is a config
change rather than an edit scattered across modules.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------- paths

ROOT = Path(os.environ.get("PERCH_HOME", Path.home() / ".perch"))
MEMORY_DIR = ROOT / "memory"          # the truth: one Markdown file per item
INDEX_DB = ROOT / "index.sqlite3"     # derived. Delete it and it rebuilds
CAPTURES = ROOT / "captures"
LOG_DIR = ROOT / "logs"

# --------------------------------------------------------------- model routing

OLLAMA_URL = os.environ.get("PERCH_OLLAMA", "http://localhost:11434")
LOCAL_MODEL = os.environ.get("PERCH_LOCAL_MODEL", "qwen2.5:3b")
EMBED_MODEL = os.environ.get("PERCH_EMBED_MODEL", "nomic-embed-text")

API_BASE = os.environ.get("PERCH_API_BASE")      # any OpenAI-compatible endpoint
API_KEY = os.environ.get("PERCH_API_KEY")
API_MODEL = os.environ.get("PERCH_API_MODEL", "gpt-4o-mini")

# Default route. "local" | "cloud" | "auto"  (auto = cloud if configured, else local)
DEFAULT_ROUTE = os.environ.get("PERCH_ROUTE", "auto")

# Global privacy default (§7.3 mechanism 3). When True everything stays local
# unless the user explicitly escalates.
PRIVATE_BY_DEFAULT = os.environ.get("PERCH_PRIVATE_DEFAULT", "0") == "1"

# ------------------------------------------------------------------- retrieval

OVERFETCH = 30          # candidates pulled before ranking, per eligible class
PROBE_FLOOR = 0.22      # a class joins the eligible set if its best item reaches this.
                        # Deliberately low: routing is permissive, admission is strict.
MARGIN_ALPHA = 0.62     # an item must reach this fraction of its class's best
MAX_ITEMS = 12          # hard ceiling on admitted items, before the budget bites

# Reserves carved out of the model's context window before memory gets any.
RESERVE_RESPONSE = 1024
RESERVE_SYSTEM = 400
RESERVE_TOOLS = 700     # tool schemas compete for the same budget (see C1)

# Rough tokens-per-character. Deliberately conservative -- overestimating the
# prompt is safe, underestimating it truncates the answer.
CHARS_PER_TOKEN = 3.6

# ----------------------------------------------------------------- OS triggers

# Ctrl+Shift+<letter> is heavily used by browsers, IDEs and office apps --
# Ctrl+Shift+C alone is "Inspect Element" in every Chromium browser. When
# RegisterHotKey loses that collision it does not error; the keystroke just
# falls straight through to whatever has focus, which is how "the shortcut
# opens the browser's inspector" happens with no warning at all. Ctrl+Alt is
# far less contested (the launcher-app convention -- PowerToys Run ships
# Alt+Space by default for the same reason), so that is the default here.
# Override per-binding with PERCH_HOTKEY_SELECTION etc. if it still collides
# on a given machine, e.g. PERCH_HOTKEY_SELECTION="ctrl+alt+shift+space".
_MOD_BITS = {"ctrl": 0x0002, "control": 0x0002, "alt": 0x0001, "shift": 0x0004}
_NAMED_VK = {"space": 0x20, "tab": 0x09, "enter": 0x0D}


def parse_combo(spec: str) -> tuple[int, int]:
    """'ctrl+alt+space' -> (MOD_CONTROL|MOD_ALT, VK_SPACE). Letters/digits use
    their ASCII code directly, which is also the Win32 virtual-key code for
    the unshifted key -- no separate VK table needed for those."""
    mods = 0
    vk: int | None = None
    for token in (p.strip().lower() for p in spec.split("+") if p.strip()):
        if token in _MOD_BITS:
            mods |= _MOD_BITS[token]
        elif token in _NAMED_VK:
            vk = _NAMED_VK[token]
        elif len(token) == 1:
            vk = ord(token.upper())
        else:
            raise ValueError(f"unrecognised hotkey token {token!r} in {spec!r}")
    if vk is None:
        raise ValueError(f"no key given in hotkey spec {spec!r}")
    return mods, vk


def describe_combo(mods: int, vk: int) -> str:
    names = [n.title() for n, bit in (("ctrl", 0x0002), ("alt", 0x0001), ("shift", 0x0004))
             if mods & bit]
    key = next((n.title() for n, code in _NAMED_VK.items() if code == vk), chr(vk))
    return "+".join(names + [key])


HOTKEY_SELECTION = parse_combo(os.environ.get("PERCH_HOTKEY_SELECTION", "ctrl+alt+space"))
HOTKEY_SCREENSHOT = parse_combo(os.environ.get("PERCH_HOTKEY_SCREENSHOT", "ctrl+alt+s"))
HOTKEY_PLAIN = parse_combo(os.environ.get("PERCH_HOTKEY_PLAIN", "ctrl+alt+p"))

# Collisions are inherently machine-dependent -- testing on one development
# machine found Ctrl+Alt+Space itself already owned by something else
# running there, which is exactly the failure mode this whole scheme exists
# to survive. So every trigger also carries a short list of fallbacks tried
# automatically, in order, before giving up -- see HotkeyListener.bind().
HOTKEY_SELECTION_FALLBACKS = [parse_combo(c) for c in
    ["ctrl+alt+shift+space", "ctrl+alt+j"]]
HOTKEY_SCREENSHOT_FALLBACKS = [parse_combo(c) for c in
    ["ctrl+alt+shift+s", "ctrl+alt+k"]]
HOTKEY_PLAIN_FALLBACKS = [parse_combo(c) for c in
    ["ctrl+alt+shift+p", "ctrl+alt+g"]]


def ensure_dirs() -> None:
    for d in (ROOT, MEMORY_DIR, CAPTURES, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
