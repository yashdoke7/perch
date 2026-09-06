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

It is also where "read is free, write asks" (architecture Part VI) is actually
asked. _confirm_tool below is the approval callback the pipeline hands to the
tool loop; without a UI supplying one, confirming tools are refused outright.

Rendering notes: vanilla tkinter has no rounded windows or drop shadows, so the
polish here is two real Windows tricks rather than a new dependency -- a
Canvas-drawn rounded card, made to actually show rounded corners on the desktop
via wm_attributes('-transparentcolor', ...), which keys out a background colour
that nothing in the card ever uses.
"""

from __future__ import annotations

import json
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from tkinter import ttk

from .. import config
from ..core.pipeline import Pipeline, Request, Response
from ..memory import classes as mc
from ..os_layer import inject, winapi
from ..tools import registry as toolreg

# The three routes §7.2 defines. "auto" is local-then-cloud, not adaptive
# routing -- that is explicitly v2, and calling this cycle "auto" rather than
# "smart" keeps the promise honest.
ROUTES = ("auto", "local", "cloud")

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
PANEL_H = 640
MIN_W, MIN_H = 360, 420
PAD = 16
RADIUS = 16
GRIP = 16          # size of the bottom-right resize handle

# Where the user last put the panel. An overrideredirect window has no title
# bar, so drag and resize are implemented by hand below -- and once someone has
# positioned it deliberately, auto-placing it somewhere else on the next
# trigger is worse than useless. Persisted so it survives a restart.
GEOMETRY_FILE = config.ROOT / "panel_geometry.json"

# One type scale, used everywhere, instead of ad-hoc sizes per widget.
# Segoe UI Variable is the Windows 11 UI face; Segoe UI is the fallback and
# is present on every supported Windows version.
_UI = "Segoe UI Variable Display"
_UI_FALLBACK = "Segoe UI"
_MONO = "Cascadia Mono"
_MONO_FALLBACK = "Consolas"

TYPE = {
    "brand":   (13, "bold"),
    "title":   (11, "bold"),
    "body":    (10, "normal"),
    "small":   (9,  "normal"),
    "label":   (8,  "bold"),     # section headers: ASK, MEMORY USED
    "micro":   (8,  "normal"),
    "chip":    (8,  "normal"),
    "tiny":    (7,  "normal"),
}

_family_cache: dict[str, str] = {}

# The pipeline stages the tracker lights up, in order. These deliberately
# mirror the architecture diagram's Stage 2 and 3 -- same names, same order --
# so the demo and the diagram corroborate each other rather than being two
# separate stories the reviewer has to reconcile.
STAGES = [
    ("route", "route"),
    ("rank", "rank"),
    ("gate", "gate"),
    ("pack", "pack"),
    ("model", "model"),
]


def _resolve_family(preferred: str, fallback: str) -> str:
    """Pick the nicer face when the OS has it, without crashing when it does not."""
    key = preferred
    if key not in _family_cache:
        try:
            available = set(tkfont.families())
        except Exception:
            available = set()
        _family_cache[key] = preferred if preferred in available else fallback
    return _family_cache[key]


def _font(size: int, weight: str = "normal", mono: bool = False) -> tuple:
    family = (_resolve_family(_MONO, _MONO_FALLBACK) if mono
              else _resolve_family(_UI, _UI_FALLBACK))
    return (family, size, weight)


def _t(role: str, mono: bool = False) -> tuple:
    """Font for a role in the type scale -- use this, not raw sizes."""
    size, weight = TYPE[role]
    return _font(size, weight, mono=mono)


def _load_geometry() -> dict:
    try:
        return json.loads(GEOMETRY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_geometry(x: int, y: int, w: int, h: int) -> None:
    try:
        GEOMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        GEOMETRY_FILE.write_text(
            json.dumps({"x": x, "y": y, "w": w, "h": h}), encoding="utf-8")
    except OSError:
        pass


def _rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class Panel:
    def __init__(self, pipeline: Pipeline, selection: str, capture_method: str,
                 host: winapi.WindowInfo | None, master: tk.Misc) -> None:
        self.pipeline = pipeline
        self.selection = selection
        self.host = host
        self.answer = ""
        self.busy = False
        self._dots_job = None
        self._streamed = False

        # A Toplevel under one long-lived root, NOT its own tk.Tk().
        #
        # Each panel used to be a fresh tk.Tk() whose show() ran mainloop(),
        # which blocked the caller until the panel closed. That serialised the
        # whole app behind whichever panel happened to be open: a hotkey press
        # while a panel was up could not be serviced at all, it just queued,
        # and every queued press then fired at once when the panel was finally
        # dismissed. First trigger instant, everything after it apparently
        # frozen. One root with one mainloop, owned by __main__, fixes it.
        self.root = tk.Toplevel(master)
        self.root.title("PERCH")
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True)
        self.root.configure(bg=KEY)
        # Real rounded corners on Windows: key out a colour used nowhere in
        # the card, so the area outside the rounded polygon shows the desktop.
        self.root.wm_attributes("-transparentcolor", KEY)

        self.width, self.height = PANEL_W, PANEL_H
        self._drag_from = None
        self._resize_from = None
        self._place_beside(host)

        self.canvas = tk.Canvas(self.root, width=self.width, height=self.height,
                                bg=KEY, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        _rounded_rect(self.canvas, 1, 1, self.width - 1, self.height - 1, RADIUS,
                     fill=BG, outline=BORDER, width=1, tags="card")

        self.private = tk.BooleanVar(value=False)
        self.route = config.DEFAULT_ROUTE if config.DEFAULT_ROUTE in ROUTES else "auto"
        self._build(selection, capture_method)

        # Resize grip, bottom-right. An overrideredirect window gets no native
        # border, so this is the only way to offer resizing at all.
        self._grip = self.canvas.create_polygon(
            self.width - GRIP - 6, self.height - 6,
            self.width - 6, self.height - GRIP - 6,
            self.width - 6, self.height - 6,
            fill=BORDER, outline="")
        self.canvas.tag_bind(self._grip, "<Button-1>", self._resize_start)
        self.canvas.tag_bind(self._grip, "<B1-Motion>", self._resize_move)
        self.canvas.tag_bind(self._grip, "<ButtonRelease-1>", self._persist_geometry)
        self.canvas.tag_bind(self._grip, "<Enter>",
                             lambda _e: self.canvas.configure(cursor="size_nw_se"))
        self.canvas.tag_bind(self._grip, "<Leave>",
                             lambda _e: self.canvas.configure(cursor=""))

        self.root.bind("<Escape>", lambda _e: self._close())

    # ---------------------------------------------------------------- layout

    def _place_beside(self, host: winapi.WindowInfo | None) -> None:
        """Position the panel, preferring the user's own choice.

        Order of preference:
          1. wherever the user last dragged/resized it -- a deliberate choice
             beats any heuristic, and re-placing it every trigger is the most
             annoying thing a floating panel can do
          2. in the free space beside the host window, if there is any
          3. edge-docked, when the host is maximised and there is no free space
        """
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()

        saved = _load_geometry()
        if saved:
            w = max(MIN_W, min(int(saved.get("w", PANEL_W)), sw))
            h = max(MIN_H, min(int(saved.get("h", PANEL_H)), sh))
            # Clamp back on-screen: a monitor may have been unplugged since.
            x = max(0, min(int(saved.get("x", 0)), sw - w))
            y = max(0, min(int(saved.get("y", 0)), sh - h))
            self.width, self.height = w, h
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            return

        w = PANEL_W
        h = min(PANEL_H, sh - 100)
        if host is None:
            x, y = sw - w - 40, 70
        else:
            gap = 14
            if host.right + gap + w <= sw:          # free space to the right
                x = host.right + gap
            elif host.left - gap - w >= 0:          # free space to the left
                x = host.left - gap - w
            else:                                    # host is maximised
                x = sw - w - 20
            y = max(30, min(host.top + 30, sh - h - 40))

        self.width, self.height = w, h
        self.root.geometry(f"{w}x{h}+{int(x)}+{int(y)}")

    # ------------------------------------------------------- drag and resize

    def _bind_drag(self, widget) -> None:
        """Make `widget` a drag handle for the whole window."""
        widget.bind("<Button-1>", self._drag_start, add="+")
        widget.bind("<B1-Motion>", self._drag_move, add="+")
        widget.bind("<ButtonRelease-1>", self._persist_geometry, add="+")
        widget.configure(cursor="fleur")

    def _drag_start(self, event) -> None:
        self._drag_from = (event.x_root, event.y_root,
                           self.root.winfo_x(), self.root.winfo_y())

    def _drag_move(self, event) -> None:
        if not getattr(self, "_drag_from", None):
            return
        px, py, wx, wy = self._drag_from
        self.root.geometry(f"+{wx + event.x_root - px}+{wy + event.y_root - py}")

    def _resize_start(self, event) -> None:
        self._resize_from = (event.x_root, event.y_root,
                             self.root.winfo_width(), self.root.winfo_height())

    def _resize_move(self, event) -> None:
        if not getattr(self, "_resize_from", None):
            return
        px, py, w0, h0 = self._resize_from
        w = max(MIN_W, w0 + event.x_root - px)
        h = max(MIN_H, h0 + event.y_root - py)
        self.width, self.height = w, h
        self.root.geometry(f"{w}x{h}")
        self._relayout()

    def _persist_geometry(self, _event=None) -> None:
        try:
            _save_geometry(self.root.winfo_x(), self.root.winfo_y(),
                           self.root.winfo_width(), self.root.winfo_height())
        except tk.TclError:
            pass

    def _relayout(self) -> None:
        """Redraw the rounded card and reflow contents after a resize."""
        try:
            w, h = self.root.winfo_width(), self.root.winfo_height()
            self.canvas.configure(width=w, height=h)
            self.canvas.delete("card")
            _rounded_rect(self.canvas, 1, 1, w - 1, h - 1, RADIUS,
                         fill=BG, outline=BORDER, width=1, tags="card")
            self.canvas.tag_lower("card")
            self.canvas.coords(self._body_window, w // 2, h // 2)
            self.canvas.itemconfigure(self._body_window,
                                      width=w - 2 * PAD, height=h - 2 * PAD)
            self.canvas.coords(self._grip,
                               w - GRIP - 6, h - 6,
                               w - 6, h - GRIP - 6,
                               w - 6, h - 6)
            self.canvas.tag_raise(self._grip)
        except (tk.TclError, AttributeError):
            pass

    def _card(self, parent, **kw):
        f = tk.Frame(parent, bg=kw.pop("bg", CARD), **kw)
        return f

    def _label(self, parent, text, fg=MUTED, role="small", **kw):
        lbl = tk.Label(parent, text=text, bg=kw.pop("bg", BG), fg=fg,
                       font=_t(role, mono=kw.pop("mono", False)),
                       anchor="w", justify="left", **kw)
        return lbl

    def _build(self, selection: str, capture_method: str) -> None:
        outer = tk.Frame(self.canvas, bg=BG)
        self._body_window = self.canvas.create_window(
            self.width // 2, self.height // 2, window=outer,
            width=self.width - 2 * PAD, height=self.height - 2 * PAD)
        outer.pack_propagate(False)

        # ---- header: brand, privacy pill, close --------------------------
        # The header doubles as the title bar: overrideredirect removed the
        # real one, so this is what the user grabs to move the panel.
        header = tk.Frame(outer, bg=BG)
        header.pack(fill="x")
        brand = self._label(header, "◆ PERCH", ACCENT, "brand")
        brand.pack(side="left")
        tk.Button(header, text="✕", command=self._close, bg=BG, fg=MUTED,
                 activebackground=CARD, activeforeground=FG, bd=0,
                 font=_t("body"), cursor="hand2").pack(side="right")
        self.privacy_pill = tk.Label(header, text="cloud allowed", bg=CARD_ALT, fg=MUTED,
                                     font=_t("micro"), padx=8, pady=2)
        self.privacy_pill.pack(side="right", padx=(0, 8))
        self._bind_drag(header)
        self._bind_drag(brand)

        method = {"uia": "UI Automation", "clipboard": "clipboard",
                  "none": "nothing captured"}.get(capture_method, capture_method)
        src = self.host.title[:38] if self.host else "(unknown)"
        prov = self._label(outer, f"{src}  ·  via {method}", role="tiny", mono=True)
        prov.pack(fill="x", pady=(6, 10))
        self._bind_drag(prov)

        if selection.strip():
            sel_card = self._card(outer)
            sel_card.pack(fill="x", pady=(0, 10))
            box = tk.Text(sel_card, height=3, wrap="word", bg=CARD, fg=FG, relief="flat",
                          font=_t("small"), padx=10, pady=8, bd=0,
                          highlightthickness=1, highlightbackground=BORDER,
                          highlightcolor=BORDER)
            box.insert("1.0", selection)
            box.configure(state="disabled")
            box.pack(fill="x")
        elif capture_method == "none":
            # Say this loudly. A silently-empty capture makes the model answer
            # a question about text it never received -- which reads as the
            # model being stupid ("which company do you mean?") when in fact
            # the OS layer handed it nothing.
            warn = tk.Frame(outer, bg=CARD, highlightthickness=1,
                            highlightbackground=WARN)
            warn.pack(fill="x", pady=(0, 10))
            self._label(warn, "  no text captured from that window", WARN, "micro",
                       bg=CARD).pack(fill="x", pady=(5, 0))
            self._label(warn, "  ask anything anyway, or re-select and retry",
                       MUTED, "tiny", bg=CARD).pack(fill="x", pady=(0, 5))

        # ---- ask row --------------------------------------------------------
        ask_row = tk.Frame(outer, bg=BG)
        ask_row.pack(fill="x", pady=(0, 6))
        self._label(ask_row, "ASK", MUTED, "label").pack(side="left")
        chk = tk.Checkbutton(
            ask_row, text="🔒 Private", variable=self.private, bg=BG, fg=WARN,
            selectcolor=CARD, activebackground=BG, activeforeground=WARN,
            font=_t("micro"), bd=0, highlightthickness=0, cursor="hand2",
        )
        chk.pack(side="right")

        # §7.2 says the user chooses the route and switching is one click.
        # Until now Request.prefer_route existed and nothing ever set it, so
        # model choice -- the thing C1 is about -- was only reachable through
        # an environment variable and a restart. Cycling on click keeps it to
        # one control in a panel that has no room for a dropdown.
        self.route_btn = tk.Label(
            ask_row, text=self._route_text(), bg=BG, fg=MUTED,
            font=_t("micro"), cursor="hand2", padx=8)
        self.route_btn.pack(side="right")
        self.route_btn.bind("<Button-1>", lambda _e: self._cycle_route())
        self.private.trace_add("write", lambda *_: self._sync_route_label())

        entry_card = tk.Frame(outer, bg=CARD, highlightthickness=1,
                              highlightbackground=BORDER, highlightcolor=ACCENT)
        entry_card.pack(fill="x", pady=(0, 8))
        self.prompt = tk.Entry(entry_card, bg=CARD, fg=FG, insertbackground=FG,
                               relief="flat", font=_t("title"), bd=0)
        self.prompt.pack(fill="x", ipady=8, padx=10)
        self.prompt.bind("<Return>", lambda _e: self._ask())
        self.prompt.bind("<FocusIn>", lambda _e: entry_card.configure(highlightbackground=ACCENT))
        self.prompt.bind("<FocusOut>", lambda _e: entry_card.configure(highlightbackground=BORDER))
        self.prompt.focus_set()

        # ---- live pipeline tracker ---------------------------------------
        # The single most useful thing this panel can show during a demo: the
        # request visibly moving through the same stages as the architecture
        # diagram, with the gate reporting what it let in and kept out. A
        # frozen spinner for 15s says nothing; this says exactly what the
        # project claims to do, while it does it.
        self.stage_wrap = tk.Frame(outer, bg=BG)
        self.stage_wrap.pack(fill="x", pady=(0, 6))
        self.stage_pills: dict[str, tk.Label] = {}
        for key, text in STAGES:
            pill = tk.Label(self.stage_wrap, text=text, bg=CARD, fg=BORDER,
                            font=_t("tiny"), padx=6, pady=2)
            pill.pack(side="left", padx=(0, 3))
            self.stage_pills[key] = pill
        self.stage_detail = self._label(outer, "", MUTED, "tiny")
        self.stage_detail.pack(fill="x", pady=(0, 4))

        self.status = self._label(outer, "Enter to ask", role="micro")
        self.status.pack(fill="x", pady=(0, 8))

        # ---- answer -----------------------------------------------------
        out_card = tk.Frame(outer, bg=CARD, highlightthickness=1,
                            highlightbackground=BORDER)
        out_card.pack(fill="both", expand=True, pady=(0, 8))
        self.out = tk.Text(out_card, wrap="word", bg=CARD, fg=FG,
                           insertbackground=FG, relief="flat", font=_t("body"),
                           padx=10, pady=10, bd=0)
        self.out.pack(fill="both", expand=True)

        # ---- provenance: the auditability claim, made visible ------------
        self._label(outer, "MEMORY USED", MUTED, "label").pack(anchor="w")
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
                     bd=0, font=_t("small"), padx=10, pady=6, cursor="hand2")
        return b

    def _primary_button(self, parent, label, action):
        b = tk.Button(parent, text=label, command=lambda: self._deliver(action),
                     bg=ACCENT, fg="#0c1420", activebackground="#4a92e8",
                     activeforeground="#0c1420", bd=0, font=_t("small"),
                     padx=12, pady=6, cursor="hand2")
        return b

    def _empty_chip_note(self) -> None:
        self._label(self.chip_wrap, "(nothing asked yet)", role="micro").pack(anchor="w")

    def _close(self) -> None:
        """Idempotent: the user can dismiss, and the main loop can also close
        this panel to replace it with a newer trigger. Either order is fine."""
        if self._dots_job:
            try:
                self.root.after_cancel(self._dots_job)
            except tk.TclError:
                pass
            self._dots_job = None
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    # Public alias -- __main__ closes the previous panel when a new trigger
    # arrives, so it does not reach for a private method.
    close = _close

    # ----------------------------------------------------------------- logic

    def _ask(self) -> None:
        question = self.prompt.get().strip()
        if not question or self.busy:
            return
        self.busy = True
        self.answer = ""
        self._streamed = False
        self.out.delete("1.0", "end")
        self._reset_stages()
        self._animate_thinking()
        self.root.update_idletasks()

        req = Request(
            question=question,
            selection=self.selection,
            source_app=self.host.title if self.host else "",
            source_title=self.host.title if self.host else "",
            private_toggle=self.private.get(),
            prefer_route=None if self.route == "auto" else self.route,
        )

        # Both callbacks fire on the pipeline's worker thread, so every one
        # of them marshals back to the UI thread via after(0, ...) -- tkinter
        # is not thread-safe and touching widgets directly from the worker
        # is the classic way this kind of panel dies mid-demo.
        def on_stage(name: str, detail: str) -> None:
            self.root.after(0, lambda: self._mark_stage(name, detail))

        def on_token(text: str) -> None:
            self.root.after(0, lambda: self._append_token(text))

        def work() -> None:
            try:
                response = self.pipeline.run(req, on_stage=on_stage, on_token=on_token,
                                             on_confirm=self._confirm_tool)
            except Exception as exc:                      # noqa: BLE001
                response = Response(answer=f"(pipeline error: {exc})", trace=None)  # type: ignore[arg-type]
            self.root.after(0, lambda: self._show(response))

        threading.Thread(target=work, daemon=True).start()

    # --------------------------------------------------------- route choice

    def _route_text(self) -> str:
        if self.private.get():
            # Not a disabled control with a tooltip -- just the truth. In
            # private mode the registry enforces local regardless of what
            # this says, so showing anything else would be a lie about where
            # the request is going.
            return "route: local (forced)"
        return f"route: {self.route}"

    def _sync_route_label(self) -> None:
        try:
            self.route_btn.configure(
                text=self._route_text(),
                fg=WARN if self.private.get() else MUTED)
        except tk.TclError:
            pass

    def _cycle_route(self) -> None:
        if self.private.get():
            return                      # nothing to choose; local is enforced
        self.route = ROUTES[(ROUTES.index(self.route) + 1) % len(ROUTES)]
        self._sync_route_label()

    # --------------------------------------------------- write confirmation

    # How long the worker will wait for an answer before treating silence as
    # "no". Generous, because the user may be reading the snippet -- but not
    # unbounded, because a worker thread blocked forever on a dialog that was
    # destroyed with its panel is a leak that only shows up under demo stress.
    CONFIRM_TIMEOUT_S = 120.0

    def _confirm_tool(self, name: str, args: dict) -> bool:
        """Ask before a tool changes state outside PERCH. Called on the WORKER.

        tkinter may only be touched from the thread that owns the loop, so
        this marshals the dialog over with after(0, ...) and blocks the
        worker on an Event until the answer comes back. The dialog itself
        uses wait_window internally, which pumps the EXISTING loop -- never a
        second nested one (PERCH_OS_PRIMER.md §5.2a).

        Every path that is not an explicit yes returns False: a closed panel,
        a destroyed window, a timeout, or an exception inside the dialog. The
        one direction this must never fail in is "allowed by accident".
        """
        decided = threading.Event()
        answer = {"ok": False}

        def ask() -> None:
            try:
                answer["ok"] = bool(messagebox.askyesno(
                    "PERCH — allow this?",
                    f"The model wants to run:\n\n{toolreg.describe_call(name, args)}\n\n"
                    "This changes something outside PERCH. Allow it?",
                    parent=self.root,
                    default=messagebox.NO,
                    icon=messagebox.WARNING,
                ))
            except Exception:                             # noqa: BLE001
                answer["ok"] = False                      # a broken dialog is a "no"
            finally:
                decided.set()

        if not self.alive:
            return False
        try:
            self.root.after(0, ask)
        except tk.TclError:                               # window already gone
            return False

        if not decided.wait(self.CONFIRM_TIMEOUT_S):
            print(f"[tool] {name} refused: confirmation timed out")
            return False
        if not answer["ok"]:
            print(f"[tool] {name} refused by the user")
        return answer["ok"]

    # ------------------------------------------------------- stage tracker

    def _reset_stages(self) -> None:
        for pill in self.stage_pills.values():
            pill.configure(bg=CARD, fg=BORDER)
        self.stage_detail.configure(text="")

    def _mark_stage(self, name: str, detail: str) -> None:
        # "tool" is not one of the five pills -- it can fire repeatedly inside
        # the model stage, so it shows in the detail line instead.
        if name == "tool":
            self.stage_detail.configure(text=f"calling {detail}…", fg=ACCENT)
            return
        pill = self.stage_pills.get(name)
        if pill is None:
            return
        # The gate is the contribution, so it gets its own colour: red when it
        # abstained (a correct, deliberate refusal), green when it admitted.
        if name == "gate":
            colour = BAD if detail == "abstained" else GOOD
        else:
            colour = ACCENT
        pill.configure(bg=CARD_ALT, fg=colour)
        if detail:
            self.stage_detail.configure(text=f"{name}: {detail}", fg=MUTED)

    def _append_token(self, text: str) -> None:
        if not self._streamed:
            self._streamed = True
            self.out.delete("1.0", "end")
            self.busy = False          # stop the dots; real output is arriving
            if self._dots_job:
                self.root.after_cancel(self._dots_job)
                self._dots_job = None
            self.status.configure(text="answering…")
        self.answer += text
        self.out.insert("end", text)
        self.out.see("end")

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

        # If tokens already streamed in, the text is on screen and correct --
        # re-inserting the full answer here would duplicate it. Only paint
        # when nothing streamed (cloud path, stub, tool-loop turns, errors).
        if not self._streamed:
            self.answer = response.answer
            self.out.delete("1.0", "end")
            self.out.insert("1.0", response.answer)
        else:
            self.answer = response.answer or self.answer

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
            self._label(self.chip_wrap, "(no trace)", role="micro").pack(anchor="w")
            return

        if not trace.admitted and not trace.dropped and not trace.rejected_classes:
            self._empty_chip_note()
            return

        for scored in trace.admitted[: self.MAX_ADMITTED_SHOWN]:
            self._chip(scored.item.cls, scored.item.title, scored.score, admitted=True)
        extra = len(trace.admitted) - self.MAX_ADMITTED_SHOWN
        if extra > 0:
            self._label(self.chip_wrap, f"+ {extra} more admitted (see console)",
                       MUTED, "tiny").pack(anchor="w", pady=(0, 4))

        if trace.abstained:
            note = tk.Frame(self.chip_wrap, bg=BG)
            note.pack(fill="x", pady=(4, 4))
            tk.Label(note, text="●", fg=BAD, bg=BG, font=_t("micro")).pack(side="left")
            self._label(note, " nothing cleared its floor — answering from general "
                        "knowledge", BAD, "micro").pack(side="left")

        for scored in trace.dropped[: self.MAX_DROPPED_SHOWN]:
            self._chip(scored.item.cls, scored.item.title, scored.score,
                      admitted=False, reason=scored.reason)
        extra_d = len(trace.dropped) - self.MAX_DROPPED_SHOWN
        if extra_d > 0:
            self._label(self.chip_wrap, f"+ {extra_d} more dropped (see console)",
                       MUTED, "tiny").pack(anchor="w")

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
                font=_t("tiny")).pack(side="left", padx=(0, 4))

        lock = "🔒 " if mc.is_private_class(cls_name) else ""
        lbl = tk.Label(inner, text=f"{lock}{cls_name}  {title[:36]}", bg=chip["bg"],
                       fg=FG if admitted else MUTED,
                       font=_t("chip"))
        if not admitted:
            f = tkfont.Font(lbl, lbl.cget("font"))
            f.configure(overstrike=1)
            lbl.configure(font=f)
        lbl.pack(side="left")

        if admitted:
            tk.Label(inner, text=f" {score:.2f}", bg=chip["bg"], fg=MUTED,
                     font=_t("tiny")).pack(side="left")
        elif reason:
            self._label(wrap, f"    {reason}", MUTED, "tiny").pack(anchor="w")

    def _deliver(self, action: str) -> None:
        if not self.answer:
            self.status.configure(text="Ask something first")
            return
        hwnd = self.host.hwnd if self.host else None
        self._close()
        ok, message = inject.deliver(self.answer, hwnd, action)  # type: ignore[arg-type]
        print(f"[deliver] {'ok' if ok else 'failed'}: {message}")

    def show(self) -> None:
        """Present the panel. Returns immediately -- the root's mainloop, owned
        by __main__, keeps running so the next trigger is serviced at once."""
        self.root.deiconify()
        self.root.lift()
        self.prompt.focus_force()

    @property
    def alive(self) -> bool:
        try:
            return bool(self.root.winfo_exists())
        except tk.TclError:
            return False
