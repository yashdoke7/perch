"""Private mode -- declared, never inferred (architecture §7.3).

Content classification is the wrong answer here. A classifier whose false
negative leaks a company secret to a cloud API is unacceptable at any accuracy
figure, so PERCH does not look at WHAT the text says. It looks at WHERE it came
from, which it knows for free at capture time.

Four mechanisms, in precedence order:

    1. per-request toggle      the Private switch on the panel
    2. source rules            this app / this folder / this window title
    3. class-driven            admitting a health or personal item forces local
    4. global default          local unless explicitly escalated

Rules live in a plain JSON file the user can open and edit. No model is
involved anywhere in this module, and that is the point.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass
from pathlib import Path

from .. import config

RULES_FILE = config.ROOT / "private_rules.json"

DEFAULT_RULES = {
    "apps": ["keepass*", "bitwarden*", "1password*"],
    "folders": [],
    "titles": ["*confidential*", "*[private]*"],
}


@dataclass
class Decision:
    private: bool
    reason: str

    def badge(self) -> str:
        return f"PRIVATE - {self.reason}" if self.private else "cloud allowed"


def load_rules() -> dict:
    if RULES_FILE.exists():
        try:
            return json.loads(RULES_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    save_rules(DEFAULT_RULES)
    return dict(DEFAULT_RULES)


def save_rules(rules: dict) -> None:
    RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
    RULES_FILE.write_text(json.dumps(rules, indent=2), encoding="utf-8")


def decide(toggle: bool, source_app: str = "", source_title: str = "",
           source_path: str = "") -> Decision:
    """Everything except the class rule, which needs retrieval to have run."""
    if toggle:
        return Decision(True, "you switched this request to private")

    rules = load_rules()
    app = (source_app or "").lower()
    title = (source_title or "").lower()
    path = (source_path or "").replace("\\", "/").lower()

    for pattern in rules.get("apps", []):
        if fnmatch.fnmatch(app, pattern.lower()):
            return Decision(True, f"source rule: application matches {pattern!r}")

    for pattern in rules.get("titles", []):
        if fnmatch.fnmatch(title, pattern.lower()):
            return Decision(True, f"source rule: window title matches {pattern!r}")

    for folder in rules.get("folders", []):
        f = folder.replace("\\", "/").lower().rstrip("/")
        if f and path.startswith(f):
            return Decision(True, f"source rule: inside {folder}")

    if config.PRIVATE_BY_DEFAULT:
        return Decision(True, "global default is local-only")

    return Decision(False, "no rule matched")


def add_app_rule(app: str) -> None:
    rules = load_rules()
    pattern = app.lower()
    if pattern not in rules["apps"]:
        rules["apps"].append(pattern)
        save_rules(rules)
