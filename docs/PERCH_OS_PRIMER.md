# PERCH — How the OS layer works, from the ground up

**Who this is for:** anyone on the team who has written applications but never written something that
reaches *outside* its own window. It starts from first principles and ends with the full wiring of
OS → application → AI.

**Why it exists separately:** the architecture document states *what* the OS layer does. This one
explains *why any of it is possible*. Read this before touching `app/os_layer/`.

---

# PART 1 — THE FIVE IDEAS YOU NEED

Everything PERCH does at the OS level follows from five facts about how Windows works.

## 1.1 Every window has a number

Windows identifies each window by an integer called an **HWND** (*handle to a window*). Notepad's
window is an HWND. Chrome's window is an HWND. A button *inside* a window is also an HWND.

The handle is the address of a thing you do not own. **You cannot reach into another program's memory,
but you can ask Windows about its windows, and you can ask Windows to do things to them.** That
asymmetry is the entire basis of desktop integration.

```
   GetForegroundWindow()      → the HWND of whatever the user is looking at
   GetWindowRect(hwnd)        → where it is on screen: left, top, right, bottom
   GetWindowTextW(hwnd)       → its title bar text
   SetForegroundWindow(hwnd)  → ask Windows to bring it back to the front
```

**Why PERCH needs this:** to put the panel *beside* your work, we must know where your work is. To
paste an answer back, we must remember which window to return to.

> **The critical detail: we capture the HWND at the moment the hotkey fires.** One instant later our
> own panel is the foreground window, and `GetForegroundWindow()` would return *us*. Snapshot first,
> then show UI. Getting this order wrong is the single most common bug in this kind of app.

## 1.2 Programs do not run — they wait for messages

A desktop program is not a script that runs top to bottom. It is a loop that waits:

```
   while (GetMessage(&msg, ...)) {      ← blocks until Windows has something to say
       TranslateMessage(&msg);
       DispatchMessage(&msg);           ← "the mouse moved", "a key went down", "repaint yourself"
   }
```

This is the **message pump**. Windows delivers events into a per-thread queue and the program drains it.

**Why PERCH needs this:** a global hotkey is delivered *as a message*. `RegisterHotKey` tells Windows
"when this key combination is pressed anywhere, put a `WM_HOTKEY` message in my queue." If nothing is
draining that queue, the hotkey silently does nothing.

> **So the hotkey listener must own a thread with a real message loop.** In our prototype that is
> `os_layer/hotkey.py`. It uses `PeekMessageW` in a short loop rather than the blocking `GetMessageW`,
> so that `stop()` is responsive instead of hanging until the next keypress.

## 1.3 Only one window has focus, and focus is guarded

**Focus** is which window receives keystrokes. Exactly one window has it.

Windows deliberately makes stealing focus difficult — otherwise any background process could pop up
over your work and capture your typing. `SetForegroundWindow` **can and does fail**, depending on
which process last received input.

**Two consequences that shape the whole design:**

1. **Our panel must not take focus when it appears.** If it did, the host application would lose its
   selection, and "replace the selected text" would have nothing to replace. The panel is created
   non-activating and always-on-top.
2. **When we hand the answer back, the refocus can fail.** So `inject.py` checks. If refocus fails we
   **do not paste** — the answer goes to the clipboard and the panel says so. **Pasting into whatever
   window happens to be in front is far worse than not pasting.**

## 1.4 The clipboard is a shared, global, single-slot resource

There is exactly one clipboard, shared by every program. Any program can read it or write it at any
time. It is not a queue and it has no history.

This gives us a universal channel — **and an obligation.** If we use the clipboard we must put back
what was there, because the user may have been holding something in it.

```
   original = get_clipboard()          # borrow
   set_clipboard(our_text)
   send_ctrl_v()
   set_clipboard(original)             # return it, always
```

**Also: the clipboard can be locked by another process.** Any clipboard call can fail transiently, so
every access retries a few times before giving up. Real users have Excel, RDP clients and clipboard
managers fighting over it.

## 1.5 Accessibility APIs let one program read another's contents

This is the one that surprises people.

Windows ships **UI Automation (UIA)** — a documented framework whose purpose is to let assistive
software (screen readers, magnifiers, automated testing tools) inspect and control other applications.
It exposes a tree of elements, and elements advertise **patterns** describing what they support.

```
   IUIAutomation
        → GetFocusedElement()              the control the user is typing in
        → GetCurrentPattern(TextPattern)   does it expose text?
             → GetSelection()              the selected range(s)
                  → GetText(-1)            the actual string
```

> **This is a supported, permissioned, twenty-year-old API surface — not a hack, not an exploit.**
> Screen readers depend on it. RPA tools depend on it. Requiring no special privilege is exactly why
> it is the right foundation for PERCH.

**But coverage is uneven.** An application only exposes `TextPattern` if its developers implemented it.
Native controls and modern frameworks generally do. Some Electron apps, custom-drawn editors and games
do not. **This is why PERCH has two capture paths, and why the per-application coverage table is a real
deliverable (E7).**

---

# PART 2 — THE THREE TRIGGERS, MECHANICALLY

## T1 — Global hotkey

```
   RegisterHotKey(NULL, id, MOD_CONTROL|MOD_SHIFT|MOD_NOREPEAT, VK_SPACE)
   ... message loop ... WM_HOTKEY arrives ... dispatch
   UnregisterHotKey(NULL, id)      ← in a finally block, always
```

`MOD_NOREPEAT` stops key-repeat from firing it fifty times if the user holds the combination.
Registration **fails** if another program already owns that combination — so the app must detect the
failure and tell the user, not fail silently.

**Rust equivalent:** `tauri-plugin-global-shortcut`, a first-party Tauri v2 plugin.

## T2 — Reading the selection

### Path A — UI Automation *(preferred)*

Clean, no side effects, does not touch the clipboard, does not synthesise input.

```python
element = automation.GetFocusedControl()
pattern = element.GetTextPattern()
ranges  = pattern.GetSelection()
text    = "".join(r.GetText(-1) for r in ranges)
```

**Fails when:** the control does not implement `TextPattern`, the element is in a process at a higher
integrity level, or the focused element is not a text control at all.

### Path B — clipboard round-trip *(universal fallback)*

```
   1. save the user's clipboard
   2. write a unique sentinel value into the clipboard
   3. synthesise Ctrl+C into the focused window
   4. poll the clipboard until it stops being the sentinel   (~25 × 10 ms)
   5. that value is the selection
   6. restore the user's original clipboard
```

**Why the sentinel?** Without it you cannot distinguish *"the copy worked and produced the same text
that was already on the clipboard"* from *"the copy did nothing."* Writing a value that could not
possibly be the answer makes the test unambiguous.

**Synthesising the keystroke** uses `SendInput` (or `keybd_event`): press Ctrl, press C, release C,
release Ctrl. Windows delivers it to the focused window exactly as if the user had typed it.

### ⚠️ The trap: your own hotkey is still held down

**This one cost real debugging time, and it is invisible when it happens.**

PERCH is summoned by a chord — `Ctrl+Alt+J`. At the instant the callback runs, the user is *still
physically holding Ctrl and Alt*. If you synthesise `Ctrl+C` right then, the modifiers **combine**:
the target application receives **`Ctrl+Alt+C`**, which is not copy in any normal app.

The clipboard never changes. The sentinel poll times out. Capture returns empty. The panel opens with
no selection, the model is asked about text it never received — and it answers *"which company do you
mean?"*, which reads like the model being stupid when the entire fault is in the OS layer.

```
   before sending any synthetic chord:
       wait until GetAsyncKeyState says Ctrl, Alt, Shift and Win are all up
       (with a timeout -- if the user is leaning on a key, force-release it)
```

> **This is a large part of why Path A is preferred.** UI Automation reads the selection through the
> accessibility tree and synthesises nothing, so it is immune. Path B is the fallback for apps that
> expose no text — which is exactly when this bites.

> **Design rule: try A, fall back to B, record which one worked, per application.** The panel displays
> the method, so the user always knows how their text was obtained.

**Rust equivalents:** the `uiautomation` crate; `arboard` for clipboard; `SendInput` via the official
`windows` crate.

## T3 — Region screenshot

```
   create a full-screen, always-on-top, semi-transparent window
   → user drags a rectangle
   → destroy the overlay
   → capture those screen coordinates       (BitBlt / Windows.Graphics.Capture / ImageGrab)
   → optional OCR to text
```

The overlay is why the drag feels like a screenshot tool: it dims the desktop and gives the crosshair
something to draw on. Nothing is captured until the mouse is released.

---

# PART 3 — PLACING THE PANEL

```
   host = GetForegroundWindow()            ← snapshot BEFORE showing anything
   rect = GetWindowRect(host)

   if rect.right + gap + PANEL_W <= screen_width:   x = rect.right + gap      # dock right
   elif rect.left - gap - PANEL_W >= 0:             x = rect.left - gap - PANEL_W   # dock left
   else:                                            x = screen_width - PANEL_W - 20 # hug the edge
```

**Window flags that matter:**

| Flag | Why |
|---|---|
| always-on-top | it must sit above the host window |
| **non-activating** | it must not take focus, or the host loses its selection |
| no title bar | it is an overlay, not an application window |
| skip taskbar | it is summoned, not launched |
| transparent | rounded corners and non-rectangular shapes |

**Tauri v2 exposes all of these as configuration** — `alwaysOnTop`, `skipTaskbar`, `transparent`,
`decorations: false` — plus `setIgnoreCursorEvents` for click-through on transparent regions.

---

# PART 4 — EDIT IN PLACE

**The insight the whole product rests on:**

> ### In every Windows text field, pasting while text is selected *replaces* that text.

That is standard edit-control behaviour, implemented by Windows and honoured by every framework built
on it. **So we do not need an Outlook plugin, a Word plugin and a VS Code extension. We need the
clipboard and a keystroke.**

```
   1. clipboard ← the answer
   2. SetForegroundWindow(saved_hwnd)     ← may fail; check it
   3. brief pause (~80 ms)                ← let the focus change actually land
   4. SendInput Ctrl+V
   5. brief pause (~120 ms)               ← let the target read the clipboard before we change it
   6. clipboard ← the user's original contents
```

**The two pauses are not superstition.** Focus changes and clipboard reads are asynchronous; the target
application processes them on its own message loop. Restoring the clipboard too early means the target
pastes the wrong thing.

**Three actions:** `Replace` (overwrite the selection) · `Insert after` (prefix a newline, leave the
original) · `Copy only` (clipboard, change nothing — the safe default when refocus fails).

---

# PART 5 — HOW OS, APPLICATION AND AI WIRE TOGETHER

## 5.1 The three processes

```
   ┌──────────────────────────────────────────────────────────────┐
   │  SHELL / OS LAYER          Rust (Tauri v2) — Python in Phase 1│
   │  hotkeys · UIA · clipboard · window mgmt · tray · panel window│
   └──────────────────────────────────────────────────────────────┘
                    │  local IPC (JSON over stdio / localhost)
   ┌──────────────────────────────────────────────────────────────┐
   │  AGENT CORE                Python                            │
   │  intent · class router · ranker · admission · packer · tools │
   │  memory store (Markdown files + SQLite index)                │
   └──────────────────────────────────────────────────────────────┘
                    │  HTTP
   ┌──────────────────────────────────────────────────────────────┐
   │  MODEL              Ollama on localhost  ▸  or a cloud API   │
   └──────────────────────────────────────────────────────────────┘
```

**Why split shell and core at all?** Because the OS work must be in a language with first-class Win32
bindings (Rust), and the ML work must be in the language with the ecosystem (Python). The boundary is a
narrow JSON protocol, which also means **either side can be replaced without touching the other** — and
is why the Phase 1 prototype can implement both sides in Python and still be a faithful rehearsal.

## 5.2 One request, following the data

| # | Where | What happens |
|---|---|---|
| 1 | **OS** | `WM_HOTKEY` arrives on the listener thread |
| 2 | **OS** | snapshot host: HWND, title, rect, process name, document path if available |
| 3 | **OS** | capture selection — UIA, else clipboard round-trip |
| 4 | **Shell** | panel opens beside the host, non-activating; shows the selection and its provenance |
| 5 | **Shell → Core** | `{question, selection, source: {app, title, path}, private: bool}` |
| 6 | **Core** | **privacy decision first** — source rules, toggle, global default |
| 7 | **Core** | intent → domain, scope, does this need memory at all |
| 8 | **Core** | class router → eligible classes |
| 9 | **Core** | retrieve → rank → **admission gate** → admitted set (possibly empty) |
| 10 | **Core** | if any admitted item is Health or Personal → **force local** |
| 11 | **Core** | packer fills the budget from `context_window(model)` |
| 12 | **Core → Model** | stream; run the tool loop; each tool result re-enters the budget |
| 13 | **Core → Shell** | answer + which items were used + which were dropped and why + which model |
| 14 | **Shell** | panel renders answer and provenance |
| 15 | **OS** | user presses Replace → clipboard → refocus HWND → `Ctrl+V` → restore clipboard |
| 16 | **Core** | capped Episodic write. **Nothing enters typed memory without the user asking** |

## 5.2a ⚠️ One UI thread, one event loop — never block it

**The second trap, and it looks like "the app got slow" rather than like a bug.**

A GUI toolkit runs a single event loop on one thread. Every trigger, every repaint, every keystroke is
serviced by that loop. **So anything that blocks it blocks everything.**

The first version gave each panel its own root window and ran its own loop:

```
   trigger → build panel → panel.mainloop()      ← blocks here until closed
           → (only now) look for the next trigger
```

Which means: while a panel is open, **the hotkey cannot be serviced at all.** The keypress is
registered by Windows, delivered to our listener thread, put on the queue — and then sits there,
because the thread that drains the queue is parked inside a nested loop. Since a panel stays up until
dismissed, and the natural habit is to read the answer and then trigger again somewhere else, the
first shortcut felt instant and every one after it felt broken. Dismissing the panel then fired the
whole backlog at once.

**The rule:**

> **One root window and one `mainloop()` for the life of the process.** Extra windows are *children*
> of it. Long work goes on a worker thread and marshals results back with `after(0, …)`. Anything that
> needs to wait for a child window uses `wait_window()`, which pumps the **existing** loop — never a
> second nested one.

**Symptom to recognise:** the first interaction is fine, later ones queue up and arrive in a burst.
That is always a blocked event loop, never a slow component — and profiling the components (as we did:
capture flat at ~270 ms, panel construction *falling* from 774 ms to 78 ms) will show nothing wrong,
because nothing is wrong with them.

## 5.3 Where each part of the source tree lives

```
   app/
     os_layer/      winapi · hotkey · capture · inject · screenshot   ← Part 1–4 of this document
     ui/            panel · provenance · actions · settings
     core/          intent · router · ranker · admission · packer
     memory/        schema · store · index · classes
     ingest/        export parsers · extraction prompts · review
     models/        registry · ollama · openai_compatible
     tools/         web · files · docs · ocr · python · memory · os
```

## 5.4 The five failure modes, and how each is handled

| Failure | Handling |
|---|---|
| Hotkey already registered by another app | registration returns false → tell the user, offer a different combination |
| UIA returns nothing | fall back to the clipboard path; record the app in the coverage table |
| Clipboard locked by another process | retry with backoff; if it still fails, open the panel with no selection |
| `SetForegroundWindow` refused | **do not paste.** Leave the answer on the clipboard and say so |
| Model unreachable | fall through the registry: local → cloud → clear error. **Never silently switch a private request to cloud** |
| Hotkey registration fails | Windows does **not** error — the keystroke just falls through to whatever has focus. Check `RegisterHotKey`'s return value, try fallback combos, and print which chord each trigger actually got. `python -m app hotkeys` probes what is free |
| Summoning modifiers still held | wait for Ctrl/Alt/Shift/Win to come up before synthesising any chord — see §2 |
| Later triggers queue up and arrive in a burst | a blocked event loop, not a slow component — see §5.2a |

---

# PART 6 — WHAT IS AND IS NOT PRIVILEGED

| | |
|---|---|
| **Needs no special privilege** | global hotkeys · foreground window and rect · clipboard read/write · synthesised input to normal apps · UIA against same-or-lower integrity processes · screen capture · always-on-top windows |
| **Would need elevation, and we do not do it** | reading another process's memory · injecting a DLL · hooking the kernel · UIA against elevated processes from a normal one · intercepting input globally with a low-level hook |
| **Practical frictions** | antivirus heuristics flag screen-reading behaviour → sign the installer, keep all capture user-initiated. Some apps expose no text → clipboard fallback. Elevated windows (Task Manager, an admin console) are opaque to a normal-privilege PERCH → acceptable |

> **Nothing in Layer 1 requires a driver, a kernel hook, an OS modification, or a special permission.
> It is the same API surface screen readers and RPA tools have used for twenty years.**

---

# PART 7 — READ THE CODE IN THIS ORDER

| # | File | What it teaches |
|---|---|---|
| 1 | `os_layer/winapi.py` | HWND, rects, clipboard with retry, synthesised keystrokes — §1.1, §1.4 |
| 2 | `os_layer/hotkey.py` | `RegisterHotKey`, the message pump, clean shutdown — §1.2 |
| 3 | `os_layer/capture.py` | both selection paths and the sentinel trick — §2 |
| 4 | `os_layer/inject.py` | focus restore, paste, clipboard restoration, refusal on failure — §4 |
| 5 | `ui/panel.py` | placement arithmetic and non-activating presentation — §3 |
| 6 | `core/pipeline.py` | the whole request path in one file — §5.2 |

**Then run it, and watch the console.** Every trigger prints the host window, the capture method, the
routed classes, what the gate admitted and dropped, and which model answered. **The log is the
architecture, made visible.**
