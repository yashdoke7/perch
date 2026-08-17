"""The panel -- the product surface (architecture §5.2).

Not "one of two surfaces". The panel IS PERCH: it appears beside your work,
sized not to occlude it, and Escape dismisses it. A short question never opens
a window. The full view is this same panel expanded -- a SIZE, not a
destination.

What it must show, and why each one is not decoration:

    provenance      which app the text came from, and by which capture path
    privacy         private or not, and the REASON, before you send
    memory used     which items were injected
    memory dropped  which were not, AND WHY -- this is the auditability that
                    a learned gate cannot offer, so it has to be visible
    model           which model answered, local or cloud
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from ..core.pipeline import Pipeline, Request, Response
from ..os_layer import inject, winapi

BG = "#16161a"
CARD = "#1e1e24"
FG = "#e8e6e3"
MUTED = "#8b8a87"
ACCENT = "#4da3ff"
GOOD = "#5ac47f"
WARN = "#e0a458"
DROP = "#7a6f6f"

PANEL_W = 460
PAD = 14


class Panel:
    def __init__(self, pipeline: Pipeline, selection: str, capture_method: str,
                 host: winapi.WindowInfo | None) -> None:
        self.pipeline = pipeline
        self.selection = selection
        self.host = host
        self.answer = ""
        self.busy = False

        self.root = tk.Tk()
        self.root.title("PERCH")
        self.root.configure(bg=BG)
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self._place_beside(host)
        self.private = tk.BooleanVar(value=False)
        self._build(selection, capture_method)
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

    # ---------------------------------------------------------------- layout

    def _place_beside(self, host: winapi.WindowInfo | None) -> None:
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        height = min(660, sh - 100)
        if host is None:
            x, y = sw - PANEL_W - 40, 70
        else:
            gap = 12
            if host.right + gap + PANEL_W <= sw:
                x = host.right + gap
            elif host.left - gap - PANEL_W >= 0:
                x = host.left - gap - PANEL_W
            else:
                x = sw - PANEL_W - 20
            y = max(30, min(host.top + 30, sh - height - 40))
        self.root.geometry(f"{PANEL_W}x{height}+{int(x)}+{int(y)}")

    def _label(self, parent, text, fg=MUTED, size=9, bold=False, **kw):
        font = ("Segoe UI", size, "bold") if bold else ("Segoe UI", size)
        lbl = tk.Label(parent, text=text, bg=kw.pop("bg", BG), fg=fg, font=font,
                       anchor="w", justify="left", **kw)
        return lbl

    def _build(self, selection: str, capture_method: str) -> None:
        outer = tk.Frame(self.root, bg=BG, padx=PAD, pady=PAD)
        outer.pack(fill="both", expand=True)

        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x")
        self._label(header, "PERCH", ACCENT, 12, True).pack(side="left")
        self._label(header, "Esc to dismiss").pack(side="right")

        method = {"uia": "UI Automation", "clipboard": "clipboard",
                  "none": "nothing captured"}.get(capture_method, capture_method)
        src = self.host.title[:40] if self.host else "(unknown)"
        self._label(outer, f"from  {src}   ·   via {method}",
                    wraplength=PANEL_W - 2 * PAD).pack(fill="x", pady=(8, 6))

        if selection.strip():
            box = tk.Text(outer, height=4, wrap="word", bg=CARD, fg=FG, relief="flat",
                          font=("Segoe UI", 9), padx=8, pady=6)
            box.insert("1.0", selection)
            box.configure(state="disabled")
            box.pack(fill="x", pady=(0, 10))

        ask = tk.Frame(outer, bg=BG)
        ask.pack(fill="x")
        self._label(ask, "ASK", MUTED, 8, True).pack(side="left")
        tk.Checkbutton(ask, text="Private", variable=self.private, bg=BG, fg=WARN,
                       selectcolor=CARD, activebackground=BG, activeforeground=WARN,
                       font=("Segoe UI", 8), bd=0, highlightthickness=0).pack(side="right")

        self.prompt = tk.Entry(outer, bg=CARD, fg=FG, insertbackground=FG,
                               relief="flat", font=("Segoe UI", 11))
        self.prompt.pack(fill="x", ipady=7, pady=(4, 8))
        self.prompt.bind("<Return>", lambda _e: self._ask())
        self.prompt.focus_set()

        self.status = self._label(outer, "Enter to ask")
        self.status.pack(fill="x")

        self.out = tk.Text(outer, height=10, wrap="word", bg=CARD, fg=FG,
                           insertbackground=FG, relief="flat", font=("Segoe UI", 10),
                           padx=8, pady=8)
        self.out.pack(fill="both", expand=True, pady=(8, 8))

        # ---- provenance: the auditability claim, made visible ----
        self._label(outer, "CONTEXT USED", MUTED, 8, True).pack(anchor="w")
        self.prov = tk.Text(outer, height=6, wrap="word", bg=BG, fg=MUTED,
                            relief="flat", font=("Consolas", 8), padx=0, pady=2)
        self.prov.tag_configure("in", foreground=GOOD)
        self.prov.tag_configure("out", foreground=DROP)
        self.prov.tag_configure("meta", foreground=ACCENT)
        self.prov.insert("1.0", "(nothing asked yet)")
        self.prov.configure(state="disabled")
        self.prov.pack(fill="x", pady=(2, 10))

        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill="x")
        for label, action in (("Replace", "replace"),
                              ("Insert after", "insert_after"),
                              ("Copy", "copy_only")):
            ttk.Button(actions, text=label,
                       command=lambda a=action: self._deliver(a)).pack(side="left", padx=(0, 6))

    # ----------------------------------------------------------------- logic

    def _ask(self) -> None:
        question = self.prompt.get().strip()
        if not question or self.busy:
            return
        self.busy = True
        self.status.configure(text="thinking…")
        self.out.delete("1.0", "end")
        self.root.update_idletasks()

        req = Request(
            question=question,
            selection=self.selection,
            source_app=self.host.title if self.host else "",
            source_title=self.host.title if self.host else "",
            private_toggle=self.private.get(),
        )

        def work() -> None:
            try:
                response = self.pipeline.run(req)
            except Exception as exc:                      # noqa: BLE001
                response = Response(answer=f"(pipeline error: {exc})", trace=None)  # type: ignore[arg-type]
            self.root.after(0, lambda: self._show(response))

        threading.Thread(target=work, daemon=True).start()

    def _show(self, response: Response) -> None:
        self.busy = False
        self.answer = response.answer
        self.out.insert("1.0", response.answer)

        trace = response.trace
        self.prov.configure(state="normal")
        self.prov.delete("1.0", "end")
        if trace is None:
            self.prov.insert("end", "no trace\n")
        else:
            for line in trace.lines():
                tag = "meta"
                if line.strip().startswith("+"):
                    tag = "in"
                elif line.strip().startswith(("-", "x")) or "ABSTAIN" in line:
                    tag = "out"
                self.prov.insert("end", line + "\n", tag)
            print("\n".join("  " + l for l in trace.lines()))
        self.prov.configure(state="disabled")

        self.status.configure(
            text=f"{trace.model} · {trace.privacy}" if trace else "done"
        )

    def _deliver(self, action: str) -> None:
        if not self.answer:
            self.status.configure(text="Ask something first")
            return
        hwnd = self.host.hwnd if self.host else None
        self.root.destroy()
        ok, message = inject.deliver(self.answer, hwnd, action)  # type: ignore[arg-type]
        print(f"[deliver] {'ok' if ok else 'failed'}: {message}")

    def show(self) -> None:
        self.root.mainloop()
