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

HOTKEY_SELECTION = ("ctrl+shift", 0x20)   # Space
HOTKEY_SCREENSHOT = ("ctrl+shift", 0x53)  # S
HOTKEY_PLAIN = ("ctrl+shift", 0x50)       # P


def ensure_dirs() -> None:
    for d in (ROOT, MEMORY_DIR, CAPTURES, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
