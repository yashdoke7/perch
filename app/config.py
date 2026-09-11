"""Paths, tunables and environment wiring.

Everything the pipeline can be tuned by lives here, so an ablation is a config
change rather than an edit scattered across modules.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_VERSION = "0.8.0"

# ---------------------------------------------------------------------- paths

ROOT = Path(os.environ.get("PERCH_HOME", Path.home() / ".perch"))
MEMORY_DIR = ROOT / "memory"          # the truth: one Markdown file per item
INDEX_DB = ROOT / "index.sqlite3"     # derived. Delete it and it rebuilds
CAPTURES = ROOT / "captures"
LOG_DIR = ROOT / "logs"

# --------------------------------------------------------------- model routing

# 127.0.0.1, NOT localhost, and the difference is not cosmetic.
#
# Ollama binds IPv4 only by default. On Windows "localhost" resolves to ::1
# first, so every call opens an IPv6 connection that nothing answers, waits out
# a ~2 second timeout, and only then falls back to 127.0.0.1. Measured on this
# machine: 2051 ms per embeddings call via localhost against 42 ms via
# 127.0.0.1 -- a 50x penalty paid on EVERY embedding and EVERY generation.
#
# It was invisible for a long time because the fallback embedder needs no
# network at all, so the cost only appeared once a real embedder was running --
# which is also when it mattered most. E6 caught it: "retrieval latency" of
# 2036 ms that was almost entirely a DNS-then-timeout dance against ourselves.
#
# Override with PERCH_OLLAMA if your Ollama listens elsewhere (OLLAMA_HOST=::
# makes it bind IPv6 too, in which case localhost is fine again).
OLLAMA_URL = os.environ.get("PERCH_OLLAMA", "http://127.0.0.1:11434")
LOCAL_MODEL = os.environ.get("PERCH_LOCAL_MODEL", "qwen2.5:3b")

# ★ The context window PERCH REQUESTS from Ollama, and the number the whole
# budget is computed from. It is sent as options.num_ctx on every call.
#
# This has to be requested, not assumed, and that is Contribution 1's whole
# foundation. Ollama's default num_ctx is 4096 REGARDLESS of what the model
# supports -- qwen2.5:3b advertises 32768 and Ollama still serves 4096 unless
# told otherwise. Measured here: a ~15,000-token prompt came back with
# prompt_eval_count = 4095 by default and 8191 with num_ctx=8192. Everything
# past the limit is discarded silently.
#
# So the packer was carefully evicting memory to fit a 6068-token budget
# derived from a hardcoded 8192, while Ollama served 4096 and threw the
# overflow away -- and it truncates from the front, which is exactly where the
# system prompt and the admitted memory sit. Every budget measurement in
# Part X was computed against a window that did not exist.
#
# 8192 is a deliberate middle: comfortably above the 4096 default, small
# enough that a 3B model still fits in modest VRAM. Raise it if you have the
# memory; registry.available() caps it at what the model actually supports.
NUM_CTX = int(os.environ.get("PERCH_NUM_CTX", "8192"))
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
MARGIN_ALPHA = 0.75     # an item must reach this fraction of its class's best.
                        # Fitted with the floors by E3 (was a hand-set 0.62).
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


# Space, S and P under Ctrl+Alt all turned out to be taken on the development
# machine -- as did Ctrl+Alt+Shift+Space, which on that machine opens an emoji
# panel. Preinstalled vendor utilities and IMEs claim a lot of the obvious
# chords, and which ones varies per machine, so the defaults below are plain
# letters that survive probing far more often. Run `python -m app hotkeys` to
# see what is actually free where you are.
HOTKEY_SELECTION = parse_combo(os.environ.get("PERCH_HOTKEY_SELECTION", "ctrl+alt+j"))
HOTKEY_SCREENSHOT = parse_combo(os.environ.get("PERCH_HOTKEY_SCREENSHOT", "ctrl+alt+k"))
HOTKEY_PLAIN = parse_combo(os.environ.get("PERCH_HOTKEY_PLAIN", "ctrl+alt+g"))

# Collisions are inherently machine-dependent, so every trigger also carries
# fallbacks tried automatically, in order, before giving up -- see
# HotkeyListener.bind(). Deliberately non-overlapping between the three
# triggers, so one falling back cannot steal another's alternate.
HOTKEY_SELECTION_FALLBACKS = [parse_combo(c) for c in
    ["ctrl+alt+shift+j", "ctrl+shift+space"]]
HOTKEY_SCREENSHOT_FALLBACKS = [parse_combo(c) for c in
    ["ctrl+alt+shift+k"]]
HOTKEY_PLAIN_FALLBACKS = [parse_combo(c) for c in
    ["ctrl+alt+shift+g", "ctrl+alt+q"]]


def ensure_dirs() -> None:
    for d in (ROOT, MEMORY_DIR, CAPTURES, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
