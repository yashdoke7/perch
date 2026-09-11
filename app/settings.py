"""User settings: what the Settings screen changes, persisted as plain JSON.

Precedence, highest first:

    1. environment variables   PERCH_ROUTE, PERCH_PRIVATE_DEFAULT, ...
    2. settings.json           what the user chose in the app
    3. the defaults below

Environment wins because it is how a developer or a test pins behaviour, and a
setting silently overriding an explicit env var would make that impossible to
reason about. The Settings screen shows when a value is locked by the
environment rather than pretending the toggle did something.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import config

FILE = config.ROOT / "settings.json"

DEFAULTS: dict = {
    "default_route": "auto",           # auto | local | cloud
    "private_by_default": False,
    "keep_sessions": True,
    "keep_private_sessions": False,    # see memory/sessions.py
    "session_cap": 200,
    "launch_at_login": False,
    "remember_position": True,         # else always dock beside the host app
}

# setting -> the env var that overrides it
ENV_LOCKS = {
    "default_route": "PERCH_ROUTE",
    "private_by_default": "PERCH_PRIVATE_DEFAULT",
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        stored = json.loads(FILE.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            data.update({k: v for k, v in stored.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return data


def locked() -> dict[str, str]:
    """Settings currently pinned by an environment variable: {name: env var}."""
    return {name: env for name, env in ENV_LOCKS.items() if os.environ.get(env)}


def save(changes: dict) -> dict:
    data = load()
    for key, value in changes.items():
        if key not in DEFAULTS:
            continue
        if isinstance(DEFAULTS[key], bool):
            value = bool(value)
        elif isinstance(DEFAULTS[key], int):
            value = max(10, int(value))
        elif key == "default_route" and value not in ("auto", "local", "cloud"):
            continue
        data[key] = value
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    apply(data)
    if "launch_at_login" in changes:
        set_launch_at_login(data["launch_at_login"])
    return data


def apply(data: dict | None = None) -> None:
    """Push settings into the live config, unless the environment pinned them."""
    data = data or load()
    lock = locked()
    if "default_route" not in lock:
        config.DEFAULT_ROUTE = data["default_route"]
    if "private_by_default" not in lock:
        config.PRIVATE_BY_DEFAULT = bool(data["private_by_default"])


# ------------------------------------------------------------ launch at login

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_NAME = "PERCH"


def launcher_command() -> str:
    """pythonw, so login does not open a console window -- or, when running as
    the packaged PERCH.exe, the executable itself. The installer's "start at
    sign-in" task writes this same value, so the two never disagree."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe")
    runner = Path(__file__).resolve().parent.parent / "run_perch.pyw"
    return f'"{pythonw if pythonw.exists() else exe}" "{runner}"'


def set_launch_at_login(enabled: bool) -> bool:
    """Per-user Run key only: no admin rights, removable from Task Manager."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _RUN_NAME, 0, winreg.REG_SZ, launcher_command())
            else:
                try:
                    winreg.DeleteValue(key, _RUN_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def launches_at_login() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _RUN_NAME)
            return True
    except OSError:
        return False
