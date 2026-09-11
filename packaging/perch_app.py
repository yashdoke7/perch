"""The packaged app's entry point -- what PERCH.exe runs.

    PERCH.exe            the agent: tray icon, shortcuts, the panel
    PERCH.exe open       ... and open the full view straight away
    PERCH.exe <command>  any `python -m app` subcommand (output goes to the log)

A windowed executable has no console, and a print() to nowhere raises, so
stdout and stderr go to ~/.perch/logs/perch.log -- the first place to look if
the tray icon never appears. Same rule as run_perch.pyw, for the same reason.
"""

import os
import sys
from pathlib import Path

if sys.stdout is None or sys.stderr is None:
    logs = Path(os.environ.get("PERCH_HOME", Path.home() / ".perch")) / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stream = open(logs / "perch.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = stream

from app.__main__ import main  # noqa: E402

main()
