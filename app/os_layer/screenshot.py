"""
T3 — region screenshot (§3.1).

A full-screen translucent window, the user drags a rectangle, we grab those
pixels. Same mechanism every screenshot tool on Windows uses.

The demo saves a PNG and reports its size; in the real product the image goes
into the conversation as context (and optionally through OCR to text).
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageGrab


@dataclass
class Shot:
    path: Path
    width: int
    height: int


def grab_region(save_dir: Path, master: "tk.Misc | None" = None) -> Shot | None:
    """Show the region selector; return None if the user cancels with Escape.

    Runs as a Toplevel under the application's single root when one is given,
    and waits with wait_window() rather than mainloop(). A nested mainloop()
    here would block the root's own loop for as long as the overlay is up,
    which is the same stall that used to make every trigger after the first
    feel frozen -- see the note in ui/panel.py.
    """

    box: dict[str, int] = {}

    owns_root = master is None
    root = tk.Tk() if owns_root else tk.Toplevel(master)
    root.attributes("-fullscreen", True)
    root.attributes("-alpha", 0.25)
    root.attributes("-topmost", True)
    root.configure(bg="black")
    root.config(cursor="crosshair")

    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    state = {"x0": 0, "y0": 0, "rect": None}

    def on_press(event: "tk.Event") -> None:
        state["x0"], state["y0"] = event.x_root, event.y_root
        state["rect"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#4da3ff", width=2
        )

    def on_drag(event: "tk.Event") -> None:
        if state["rect"] is not None:
            x0 = state["x0"] - root.winfo_rootx()
            y0 = state["y0"] - root.winfo_rooty()
            canvas.coords(state["rect"], x0, y0, event.x, event.y)

    def on_release(event: "tk.Event") -> None:
        box["left"] = min(state["x0"], event.x_root)
        box["top"] = min(state["y0"], event.y_root)
        box["right"] = max(state["x0"], event.x_root)
        box["bottom"] = max(state["y0"], event.y_root)
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Escape>", lambda _e: root.destroy())

    if owns_root:
        root.mainloop()
    else:
        root.grab_set()          # modal while the region is being dragged
        root.wait_window(root)   # pumps the EXISTING loop, does not nest one

    if not box or box["right"] - box["left"] < 4 or box["bottom"] - box["top"] < 4:
        return None

    image = ImageGrab.grab(
        bbox=(box["left"], box["top"], box["right"], box["bottom"]),
        all_screens=True,
    )
    save_dir.mkdir(parents=True, exist_ok=True)
    path = save_dir / "capture.png"
    image.save(path)
    return Shot(path=path, width=image.width, height=image.height)
