"""The panel -- the product surface (architecture §5.2).

Not "one of two surfaces". The panel IS PERCH: it appears beside your work,
sized not to occlude it, and Escape dismisses it. A short question never opens
a window. The full view is this same panel expanded -- a SIZE, not a
destination.

What it must show, and why each one is not decoration:

    provenance      which app the text came from, and by which capture path
    privacy         private or not, and the REASON, before you send
    memory used     which items were injected, as coloured per-class chips
    memory dropped  which were not, AND WHY -- this is the auditability that
                    a learned gate cannot offer, so it has to be visible
    model           which model answered, local or cloud

Rendering notes: vanilla tkinter has no rounded windows or drop shadows, so the
polish here is two real Windows tricks rather than a new dependency -- a
Canvas-drawn rounded card, made to actually show rounded corners on the desktop
via wm_attributes('-transparentcolor', ...), which keys out a background colour
that nothing in the card ever uses.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from ..core.pipeline import Pipeline, Request, Response
from ..memory import classes as mc
from ..os_layer import inject, winapi

# ------------------------------------------------------------------ palette

KEY = "#0b0b0d"          # transparency key -- must appear nowhere else
BG = "#17171c"
CARD = "#1f2027"
CARD_ALT = "#242530"
FG = "#eceae6"
MUTED = "#8f8d8a"
BORDER = "#33343d"
ACCENT = "#5aa7ff"
GOOD = "#57c785"
BAD = "#e2685f"
WARN = "#e2a34f"

CLASS_COLOR = {
    "identity": "#5aa7ff",
    "project": "#a78bfa",
    "academic": "#34d399",
    "career": "#f0b429",
    "health": "#fb7185",
    "personal": "#f472b6",
}

PANEL_W = 460
PAD = 16
RADIUS = 16


def _font(size: int, weight: str = "normal") -> tuple:
    family = "Segoe UI Semibold" if weight == "bold" else "Segoe UI"
    return (family, size, "bold" if weight == "bold" and family == "Segoe UI" else "normal")


def _rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class Panel:
    def __init__(self, pipeline: Pipeline, selection: str, capture_method: str,
                 host: winapi.WindowInfo | None) -> None:
        self.pipeline = pipeline
        self.selection = selection
        self.host = host
        self.answer = ""
        self.busy = False
        self._dots_job = None

        self.root = tk.Tk()
        self.root.title("PERCH")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        # Real rounded corners on Windows: key out a colour used nowhere in
        # the card, so the area outside the rounded polygon shows the desktop.
        self.root.wm_attributes("-transparentcolor", KEY)

        self.height = min(680, self.root.winfo_screenheight() - 100)
        self._place_beside(host)

        self.canvas = tk.Canvas(self.root, width=PANEL_W, height=self.height,
                                bg=KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        _rounded_rect(self.canvas, 1, 1, PANEL_W - 1, self.height - 1, RADIUS,
                     fill=BG, outline=BORDER, width=1)

        self.private = tk.BooleanVar(value=False)
        self._build(selection, capture_method)

        self.root.bind("<Escape>", lambda _e: self._close())

    # ---------------------------------------------------------------- layout

    def _place_beside(self, host: winapi.WindowInfo | None) -> None:
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if host is None:
            x, y = sw - PANEL_W - 40, 70
        else:
            gap = 14
            if host.right + gap + PANEL_W <= sw:
                x = host.right + gap
            elif host.left - gap - PANEL_W >= 0:
                x = host.left - gap - PANEL_W
            else:
                x = sw - PANEL_W - 20
            y = max(30, min(host.top + 30, sh - self.height - 40))
        self.root.geometry(f"{PANEL_W}x{self.height}+{int(x)}+{int(y)}")

    def _card(self, parent, **kw):
        f = tk.Frame(parent, bg=kw.pop("bg", CARD), **kw)
        return f

    def _label(self, parent, text, fg=MUTED, size=9, weight="normal", **kw):
        lbl = tk.Label(parent, text=text, bg=kw.pop("bg", BG), fg=fg,
                       font=_font(size, weight), anchor="w", justify="left", **kw)
        return lbl

    def _build(self, selection: str, capture_method: str) -> None:
        outer = tk.Frame(self.canvas, bg=BG)
        self.canvas.create_window(PANEL_W // 2, self.height // 2, window=outer,
                                  width=PANEL_W - 2 * PAD, height=self.height - 2 * PAD)
        outer.pack_propagate(False)

        # ---- header: brand, privacy pill, close --------------------------
        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x")
        self._label(header, "◆ PERCH", ACCENT, 12, "bold").pack(side="left")
        tk.Button(header, text="✕", command=self._close, bg=BG, fg=MUTED,
                 activebackground=CARD, activeforeground=FG, bd=0,
                 font=_font(10), cursor="hand2").pack(side="right")
        self.privacy_pill = tk.Label(header, text="cloud allowed", bg=CARD_ALT, fg=MUTED,
                                     font=_font(8), padx=8, pady=2)
        self.privacy_pill.pack(side="right", padx=(0, 8))

        method = {"uia": "UI Automation", "clipboard": "clipboard",
                  "none": "nothing captured"}.get(capture_method, capture_method)
        src = self.host.title[:38] if self.host else "(unknown)"
        self._label(outer, f"{src}  ·  via {method}", size=8).pack(fill="x", pady=(6, 8))

        if selection.strip():
            sel_card = self._card(outer)
            sel_card.pack(fill="x", pady=(0, 10))
            box = tk.Text(sel_card, height=3, wrap="word", bg=CARD, fg=FG, relief="flat",
                          font=_font(9), padx=10, pady=8, bd=0,
                          highlightthickness=1, highlightbackground=BORDER,
                          highlightcolor=BORDER)
            box.insert("1.0", selection)
            box.configure(state="disabled")
            box.pack(fill="x")

        # ---- ask row --------------------------------------------------------
        ask_row = tk.Frame(outer, bg=BG)
        ask_row.pack(fill="x", pady=(0, 6))
        self._label(ask_row, "ASK", MUTED, 8, "bold").pack(side="left")
        chk = tk.Checkbutton(
            ask_row, text="🔒 Private", variable=self.private, bg=BG, fg=WARN,
            selectcolor=CARD, activebackground=BG, activeforeground=WARN,
            font=_font(8), bd=0, highlightthickness=0, cursor="hand2",
        )
        chk.pack(side="right")

        entry_card = tk.Frame(outer, bg=CARD, highlightthickness=1,
                              highlightbackground=BORDER, highlightcolor=ACCENT)
        entry_card.pack(fill="x", pady=(0, 8))
        self.prompt = tk.Entry(entry_card, bg=CARD, fg=FG, insertbackground=FG,
                               relief="flat", font=_font(11), bd=0)
        self.prompt.pack(fill="x", ipady=8, padx=10)
        self.prompt.bind("<Return>", lambda _e: self._ask())
        self.prompt.bind("<FocusIn>", lambda _e: entry_card.configure(highlightbackground=ACCENT))
        self.prompt.bind("<FocusOut>", lambda _e: entry_card.configure(highlightbackground=BORDER))
        self.prompt.focus_set()

        self.status = self._label(outer, "Enter to ask", size=8)
        self.status.pack(fill="x", pady=(0, 8))

        # ---- answer -----------------------------------------------------
        out_card = tk.Frame(outer, bg=CARD, highlightthickness=1,
                            highlightbackground=BORDER)
        out_card.pack(fill="both", expand=True, pady=(0, 8))
        self.out = tk.Text(out_card, wrap="word", bg=CARD, fg=FG,
                           insertbackground=FG, relief="flat", font=_font(10),
                           padx=10, pady=10, bd=0)
        self.out.pack(fill="both", expand=True)

        # ---- provenance: the auditability claim, made visible ------------
        self._label(outer, "MEMORY USED", MUTED, 8, "bold").pack(anchor="w")
        self.chip_wrap = tk.Frame(outer, bg=BG)
        self.chip_wrap.pack(fill="x", pady=(4, 10))
        self._empty_chip_note()

        # ---- actions ------------------------------------------------------
        actions = tk.Frame(outer, bg=BG)
        actions.pack(fill="x")
        self._primary_button(actions, "▶  Replace", "replace").pack(side="left", padx=(0, 6))
        self._button(actions, "⤵  Insert after", "insert_after").pack(side="left", padx=(0, 6))
        self._button(actions, "⧉  Copy", "copy_only").pack(side="left")

    def _button(self, parent, label, action):
        b = tk.Button(parent, text=label, command=lambda: self._deliver(action),
                     bg=CARD_ALT, fg=FG, activebackground=BORDER, activeforeground=FG,
                     bd=0, font=_font(9), padx=10, pady=6, cursor="hand2")
        return b

    def _primary_button(self, parent, label, action):
        b = tk.Button(parent, text=label, command=lambda: self._deliver(action),
                     bg=ACCENT, fg="#0c1420", activebackground="#4a92e8",
                     activeforeground="#0c1420", bd=0, font=_font(9, "bold"),
                     padx=12, pady=6, cursor="hand2")
        return b

    def _empty_chip_note(self) -> None:
        self._label(self.chip_wrap, "(nothing asked yet)", size=8).pack(anchor="w")

    def _close(self) -> None:
        if self._dots_job:
            self.root.after_cancel(self._dots_job)
        self.root.destroy()

    # ----------------------------------------------------------------- logic

    def _ask(self) -> None:
        question = self.prompt.get().strip()
        if not question or self.busy:
            return
        self.busy = True
        self.out.delete("1.0", "end")
        self._animate_thinking()
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

    def _animate_thinking(self, tick: int = 0) -> None:
        if not self.busy:
            return
        dots = "· " * ((tick % 3) + 1)
        self.status.configure(text=f"thinking {dots}")
        self._dots_job = self.root.after(350, lambda: self._animate_thinking(tick + 1))

    def _show(self, response: Response) -> None:
        self.busy = False
        if self._dots_job:
            self.root.after_cancel(self._dots_job)
            self._dots_job = None

        self.answer = response.answer
        self.out.insert("1.0", response.answer)

        trace = response.trace
        self._render_chips(trace)

        if trace is None:
            self.status.configure(text="error")
            return

        badge = "PRIVATE" if trace.private else "cloud allowed"
        colour = WARN if trace.private else MUTED
        self.privacy_pill.configure(text=f"🔒 {badge}" if trace.private else badge, fg=colour)
        self.status.configure(text=f"{trace.model}  ·  {trace.ms} ms")

        print(f"\n[{'/'.join(trace.eligible)}] {trace.privacy}")
        for line in trace.lines():
            print("  " + line)

    # Panel is a fixed 460px width, and a single admission can legitimately
    # pull a dozen items (see the "what memory do you have" example, which
    # admits 8) -- so chips stack one per line rather than wrapping
    # horizontally, and the list is capped with an overflow note pointing at
    # the console, which prints the full trace unclipped.
    MAX_ADMITTED_SHOWN = 6
    MAX_DROPPED_SHOWN = 3

    def _render_chips(self, trace) -> None:
        for child in self.chip_wrap.winfo_children():
            child.destroy()

        if trace is None:
            self._label(self.chip_wrap, "(no trace)", size=8).pack(anchor="w")
            return

        if not trace.admitted and not trace.dropped and not trace.rejected_classes:
            self._empty_chip_note()
            return

        for scored in trace.admitted[: self.MAX_ADMITTED_SHOWN]:
            self._chip(scored.item.cls, scored.item.title, scored.score, admitted=True)
        extra = len(trace.admitted) - self.MAX_ADMITTED_SHOWN
        if extra > 0:
            self._label(self.chip_wrap, f"+ {extra} more admitted (see console)",
                       MUTED, 7).pack(anchor="w", pady=(0, 4))

        if trace.abstained:
            note = tk.Frame(self.chip_wrap, bg=BG)
            note.pack(fill="x", pady=(4, 4))
            tk.Label(note, text="●", fg=BAD, bg=BG, font=_font(8)).pack(side="left")
            self._label(note, " nothing cleared its floor — answering from general "
                        "knowledge", BAD, 8).pack(side="left")

        for scored in trace.dropped[: self.MAX_DROPPED_SHOWN]:
            self._chip(scored.item.cls, scored.item.title, scored.score,
                      admitted=False, reason=scored.reason)
        extra_d = len(trace.dropped) - self.MAX_DROPPED_SHOWN
        if extra_d > 0:
            self._label(self.chip_wrap, f"+ {extra_d} more dropped (see console)",
                       MUTED, 7).pack(anchor="w")

    def _chip(self, cls_name: str, title: str, score: float,
              admitted: bool, reason: str = "") -> None:
        colour = CLASS_COLOR.get(cls_name, MUTED)
        wrap = tk.Frame(self.chip_wrap, bg=BG)
        wrap.pack(anchor="w", fill="x", pady=(0, 3))

        chip = tk.Frame(wrap, bg=CARD_ALT if admitted else BG,
                        highlightthickness=1,
                        highlightbackground=colour if admitted else BORDER)
        chip.pack(anchor="w")

        inner = tk.Frame(chip, bg=chip["bg"])
        inner.pack(padx=6, pady=3)
        dot_fg = colour if admitted else BORDER
        tk.Label(inner, text="●", fg=dot_fg, bg=chip["bg"],
                font=_font(7)).pack(side="left", padx=(0, 4))

        lock = "🔒 " if mc.is_private_class(cls_name) else ""
        lbl = tk.Label(inner, text=f"{lock}{cls_name}  {title[:36]}", bg=chip["bg"],
                       fg=FG if admitted else MUTED,
                       font=_font(8, "bold" if admitted else "normal"))
        if not admitted:
            f = tkfont.Font(lbl, lbl.cget("font"))
            f.configure(overstrike=1)
            lbl.configure(font=f)
        lbl.pack(side="left")

        if admitted:
            tk.Label(inner, text=f" {score:.2f}", bg=chip["bg"], fg=MUTED,
                     font=_font(7)).pack(side="left")
        elif reason:
            self._label(wrap, f"    {reason}", MUTED, 7).pack(anchor="w")

    def _deliver(self, action: str) -> None:
        if not self.answer:
            self.status.configure(text="Ask something first")
            return
        hwnd = self.host.hwnd if self.host else None
        self._close()
        ok, message = inject.deliver(self.answer, hwnd, action)  # type: ignore[arg-type]
        print(f"[deliver] {'ok' if ok else 'failed'}: {message}")

    def show(self) -> None:
        self.root.mainloop()
