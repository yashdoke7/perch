# PERCH — OS layer demonstration (Phase 0)

**Purpose: prove the part of the project nobody on the team has built before.**

The application layer and the agent layer are familiar work. The open question was whether a desktop
app can genuinely reach *into other applications* on Windows — read what you selected in a PDF, place
a panel beside your editor, and write an answer back into the document you were in.

**This demo answers that question with running code, before any of the real product is designed.**

---

## What it proves

| # | Claim | Where |
|---|---|---|
| **T1** | A system-wide hotkey works regardless of which app has focus | `hotkey.py` — `RegisterHotKey` + message loop |
| **T2** | We can read the current selection **from any application** | `capture.py` — UI Automation, with clipboard fallback |
| **T3** | We can capture a screen region | `screenshot.py` — overlay + `ImageGrab` |
| **P** | The panel places itself **beside** your work, not over it | `panel.py` — `GetForegroundWindow` + `GetWindowRect` |
| **E** | **The answer edits the document you came from** | `inject.py` — focus restore + `Ctrl+V` |

> **The one that matters is E.** A chat window can only ever give you text to copy. This edits in
> place, in whatever application you were already using, with no per-app plugin.

---

## Run it

```bash
cd perch/demo
pip install -r requirements.txt
python run.py
```

| Shortcut | What happens |
|---|---|
| `Ctrl+Shift+Space` | reads your current selection, opens the panel beside that window |
| `Ctrl+Shift+S` | drag a region, then ask about it |
| `Ctrl+Shift+P` | ask with nothing selected |
| `Esc` | dismiss the panel |

**The five-second test:** open Notepad, type a clumsy sentence, select it, press `Ctrl+Shift+Space`,
ask *"make this more formal"*, press **Replace**. The sentence in Notepad changes.

### Getting real answers

Optional — the OS layer works without any model.

```bash
ollama run qwen2.5:3b          # local, free, nothing leaves the machine
```

or set `PERCH_API_BASE` and `PERCH_API_KEY` for any OpenAI-compatible endpoint
(NVIDIA NIM's free tier works). With neither, the panel returns a stub and
Replace/Insert/Copy still function.

---

## How selection capture actually works

Two paths, because no single one covers every application:

**Path A — UI Automation.** Ask the focused control for its selected text range.
`GetFocusedControl()` → `TextPattern` → `GetSelection()`. Clean, no side effects. This is the same
framework screen readers use, so it is a supported path rather than a trick.

**Path B — clipboard round-trip.** Save the clipboard, send `Ctrl+C`, read it, **put the user's
clipboard back**. Less elegant, works essentially everywhere.

The demo tries A, falls back to B, and **prints which one worked for each application**. That
per-app coverage table is a real deliverable — no competitor publishes one.

## How edit-in-place works

The whole trick is that we do not need to integrate with Word, Outlook, or VS Code:

> **In every Windows text field, pasting while text is selected replaces it.**

So: save the host window handle at trigger time → generate the answer → restore focus to that window
→ put the answer on the clipboard → send `Ctrl+V` → restore the user's clipboard. If Windows refuses
the focus change, we **do not paste** — the answer goes to the clipboard and the panel says so, because
pasting into the wrong window would be much worse than not pasting.

---

## What this is not

- **Not the product.** tkinter, single-file panel, no memory, no context assembly. The real client is
  Tauri v2 (30–50 MB idle against Electron's 150–300 MB).
- **Not the AI/ML work.** Layers 2 and 3 — context assembly under a token budget, and the memory
  system — are the technical core and are not in this demo.
- **Not doing anything privileged.** No driver, no kernel hook, no OS modification, no special
  permission. Documented user-mode APIs only.

## Mapping to the real stack

| Demo (Python) | Product (Rust / Tauri v2) |
|---|---|
| `hotkey.py` | `tauri-plugin-global-shortcut` |
| `capture.py` Path A | `uiautomation` crate |
| `capture.py` Path B / `inject.py` | `arboard` + `SendInput` via the `windows` crate |
| `panel.py` placement | Tauri window with `alwaysOnTop`, `skipTaskbar`, `transparent` |
| `screenshot.py` | `xcap` or `Windows.Graphics.Capture` |

Every row is a documented crate or first-party plugin. **Nothing in Layer 1 is speculative.**
