"""
The side panel (§3.2, §4.2).

Proves the two things that matter about the surface layer:

  1. it places itself BESIDE the window you were working in, not over it
  2. it hands the answer back through inject.deliver(), so "Replace" actually
     edits the document you were in

tkinter is deliberate for the demo — zero install, and it makes the point that
none of this depends on a heavy UI stack. The real product is Tauri v2
(30-50 MB idle vs Electron's 150-300 MB).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from . import inject, winapi

BG = "#16161a"
FG = "#e8e6e3"
MUTED = "#8b8a87"
ACCENT = "#4da3ff"
PANEL_W = 420
PAD = 14


class Panel:
    """One summoned panel. Created on trigger, destroyed on Escape."""

    def __init__(
        self,
        selection_text: str,
        capture_method: str,
        source_title: str,
        host: winapi.WindowInfo | None,
        ask: Callable[[str, str], str],
    ) -> None:
        self.host = host
        self.ask = ask
        self.answer: str = ""

        self.root = tk.Tk()
        self.root.title("PERCH")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)  # no title bar — this is an overlay, not an app
        self._place_beside(host)

        self._build(selection_text, capture_method, source_title)
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    # ---------------------------------------------------------------- layout

    def _place_beside(self, host: winapi.WindowInfo | None) -> None:
        """Dock to the right of the host window, or the left if there is no room.

        This is GetForegroundWindow + GetWindowRect doing the work — the same two
        calls the Tauri version will make.
        """
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        height = min(540, screen_h - 120)

        if host is None:
            x = screen_w - PANEL_W - 40
            y = 80
        else:
            gap = 12
            if host.right + gap + PANEL_W <= screen_w:
                x = host.right + gap           # to the right of your work
            elif host.left - gap - PANEL_W >= 0:
                x = host.left - gap - PANEL_W  # no room right, go left
            else:
                x = screen_w - PANEL_W - 20    # no room either side, hug the edge
            y = max(40, min(host.top + 40, screen_h - height - 40))

        self.root.geometry(f"{PANEL_W}x{height}+{int(x)}+{int(y)}")

    def _build(self, selection_text: str, capture_method: str, source_title: str) -> None:
        outer = tk.Frame(self.root, bg=BG, padx=PAD, pady=PAD)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x")
        tk.Label(header, text="PERCH", bg=BG, fg=ACCENT,
                 font=("Segoe UI Semibold", 12)).pack(side="left")
        tk.Label(header, text="Esc to dismiss", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right")

        # Provenance line. This is also what Private-mode source rules match on —
        # we know WHERE it came from without inspecting WHAT it says.
        method_label = {"uia": "UI Automation", "clipboard": "clipboard", "none": "nothing captured"}
        tk.Label(
            outer,
            text=f"from  {source_title[:44]}   ·   via {method_label.get(capture_method, capture_method)}",
            bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w", justify="left", wraplength=PANEL_W - 2 * PAD,
        ).pack(fill="x", pady=(8, 6))

        tk.Label(outer, text="SELECTION", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        sel = tk.Text(outer, height=5, wrap="word", bg="#1e1e24", fg=FG,
                      insertbackground=FG, relief="flat", font=("Segoe UI", 10),
                      padx=8, pady=8)
        sel.insert("1.0", selection_text or "(nothing selected — ask anything)")
        sel.configure(state="disabled")
        sel.pack(fill="x", pady=(4, 12))

        tk.Label(outer, text="ASK", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        self.prompt = tk.Entry(outer, bg="#1e1e24", fg=FG, insertbackground=FG,
                               relief="flat", font=("Segoe UI", 11))
        self.prompt.pack(fill="x", ipady=7, pady=(4, 10))
        self.prompt.bind("<Return>", lambda _e: self._run(selection_text))
        self.prompt.focus_set()

        self.status = tk.Label(outer, text="Enter to ask", bg=BG, fg=MUTED,
                               font=("Segoe UI", 9), anchor="w")
        self.status.pack(fill="x")

        self.out = tk.Text(outer, height=9, wrap="word", bg="#1e1e24", fg=FG,
                           insertbackground=FG, relief="flat", font=("Segoe UI", 10),
                           padx=8, pady=8)
        self.out.pack(fill="both", expand=True, pady=(8, 10))

        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill="x")
        self._action_button(actions, "Replace", "replace")
        self._action_button(actions, "Insert after", "insert_after")
        self._action_button(actions, "Copy", "copy_only")

    def _action_button(self, parent: tk.Frame, label: str, action: str) -> None:
        ttk.Button(parent, text=label,
                   command=lambda: self._deliver(action)).pack(side="left", padx=(0, 6))

    # ----------------------------------------------------------------- logic

    def _run(self, selection_text: str) -> None:
        question = self.prompt.get().strip()
        if not question:
            return
        self.status.configure(text="thinking...")
        self.root.update_idletasks()
        try:
            self.answer = self.ask(question, selection_text)
        except Exception as exc:
            self.answer = f"(model call failed: {exc})"
        self.out.delete("1.0", "end")
        self.out.insert("1.0", self.answer)
        self.status.configure(text="Replace edits the document you came from")

    def _deliver(self, action: str) -> None:
        if not self.answer:
            self.status.configure(text="Ask something first")
            return
        hwnd = self.host.hwnd if self.host else None
        self.root.destroy()  # get out of the way before returning focus
        ok, message = inject.deliver(self.answer, hwnd, action)  # type: ignore[arg-type]
        print(f"[deliver] {'ok' if ok else 'failed'}: {message}")

    def show(self) -> None:
        self.root.mainloop()
