"""PERCH with no console window -- for double-clicking, the Start menu, and
"start when I sign in" (Settings -> Window and startup).

pythonw has no stdout or stderr, and a print() to nowhere raises. Everything
the console would have shown goes to ~/.perch/logs/perch.log instead, which
is also the first place to look if the tray icon never appears.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.chdir(HERE)

if sys.stdout is None or sys.stderr is None:
    logs = Path(os.environ.get("PERCH_HOME", Path.home() / ".perch")) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stream = open(logs / "perch.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream

from app.__main__ import run_agent  # noqa: E402

run_agent()
