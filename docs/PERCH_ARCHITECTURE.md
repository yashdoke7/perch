# PERCH — Architecture

> **PERCH is a personal AI agent that is not trapped inside an application.**
> It lives where your desktop lives — dormant in the background, summoned by a selection, a screenshot,
> or a shortcut, anywhere in Windows. It answers in a slim panel beside your work, and it edits in
> place where you were already working. When you want a full conversation, the same agent opens a
> proper window.
>
> **And because it sits above your applications rather than inside one, it is the only place your
> personal context can live once and be used everywhere.**

**Companion:** [PERCH_REFERENCES.md](PERCH_REFERENCES.md).

---

# PART I — WHY THIS EXISTS

## 1.1 The real problem is not "which AI" — it is that your context is trapped

**Nobody uses one AI any more.**

A typical user has ChatGPT for general questions and career advice, Claude Code or Copilot for
programming, Perplexity for research, Gemini inside Docs, and AI features inside products like Canva.
**Each one holds a separate, private memory of you, and none of them can see the others.**

Verified market position:

| Fact | |
|---|---|
| ChatGPT's assistant market share fell from **~60% (early 2025) to under 45% (Q1 2026)** | people are moving constantly |
| A power user pays **$70–110/month** across ChatGPT Plus, Claude Pro, Gemini, and a coding assistant | fragmentation is expensive |
| **Users lose 15–30 minutes of context every time they switch platforms** | fragmentation is slow |
| *"Users are prioritizing **governance and data portability** over UI"* | ownership is now the deciding factor |
| **Frontier models fall below 70% task completion when a task needs stateful reasoning about the user** | PAUSE, ACM SIGKDD 2026 |

**The concrete version of this, from a real workflow:**

> Your college details, your background and your career context are in **ChatGPT**.
> Everything about your final-year project — the stack, the bugs, the decisions, the timeline — is in
> **Claude Code**, spread across dozens of sessions.
> **Neither can see the other.** So when you need to write a project summary for an application form,
> neither one can do it. ChatGPT does not know the project. Claude Code does not know the form, and
> its knowledge is scattered across sessions it will not surface unless you find the right one.
>
> **You end up doing the merge manually, in your head, every time.**

## 1.2 The thesis

> **Stop asking which AI to use. Own the context, and let every AI use it.**

**This is not a preference — it is the published lesson from the category's most expensive failures.**
Humane raised **$230M** and shipped fewer than 10,000 pins. Rabbit sold 100,000 R1s and took mass
returns. The stated conclusion:

> ### ***"AI doesn't need a new gadget — it needs to improve the tools you already use."***

## 1.3 Why no existing company will build this

**A neutral context layer is against every incumbent's business model.**

OpenAI wants you inside ChatGPT. Google wants you inside Gemini. Microsoft wants you inside Copilot.
Apple wants you on a Mac. **Highlight AI tried the neutral position, raised $50M, and pivoted to
enterprise team tooling in March 2026.**

> **A layer whose entire value is making *all* your AIs know you can only be built by someone with no
> model to sell.** That is the structural reason this position is open, and why it stays open.

---

# PART II — WHAT THE USER ACTUALLY GETS

## 2.1 The adoption move: you do not have to leave anything

Every competitor says *"switch to us."* **PERCH says: keep everything you are paying for, and we will
make all of it know who you are.**

PERCH can emit a **context block** — a compact, structured summary of the relevant parts of your
memory — that you paste into ChatGPT, Claude, Cursor, or any assistant. **Now that assistant knows
your project, your constraints, your writing style, without you retyping it.**

Nothing to give up, value on day one, and **the more AI tools you use, the more useful PERCH becomes.**

## 2.2 Memory that is built two ways

### (a) It accumulates, like every assistant's memory
As you use PERCH, it retains what matters — the same behaviour as ChatGPT's or Gemini's memory.

### (b) ⭐ It imports what is stranded in your other AIs

**This is the mechanism that solves §1.1, and it is the feature that makes people install it.**

PERCH ships **extraction prompts**. You paste one into any assistant session that contains knowledge
about you, and it returns a **structured block** you import into PERCH in one click.

**The Project block, as the worked example:**

```
   name · one-line purpose · the problem it solves
   stack, tools, versions
   architecture and pipeline decisions — and why each was chosen
   problems hit during design, and how each was resolved
   timeline: what happened when
   results, numbers, benchmarks achieved
   what remains / known limitations
```

**Run it once at the end of a project inside Claude Code, and every one of those facts is now yours,
permanently, outside that tool.**

### Where that pays off — four more worked examples

| Situation | Without PERCH | With PERCH |
|---|---|---|
| **Filling an application or scholarship form** — "describe a technical challenge you overcame in 200 words" | Open the coding AI, hunt for the right session, re-read it, summarise, rewrite to the word limit | Select the form field, ask. The project block already contains the challenge, the fix, and the result. It writes to the word limit in your tone |
| **Updating a résumé** — a new bullet for the project | Recall the metrics, find where you recorded them, condense | Ask. The results and numbers are stored; it produces bullets and you pick one |
| **An interviewer asks "walk me through a hard bug"** — you are preparing the night before | Scroll months of chat history across two tools | Ask PERCH for the three hardest problems across all your projects. It has them, because you imported them |
| **Writing an email to a professor about your project** | Re-explain the project to the AI, then re-explain the tone you want | Trigger in the compose window. Project from domain memory, tone and college from identity memory. Draft is correct first time |
| **Starting a new project that resembles an old one** | You remember there was a similar problem but not the solution | Ask. It surfaces the earlier decision and why you made it |

> **The pattern in all five: the knowledge already existed — it was just locked in a session inside a
> product that will never share it.**

## 2.3 Six capabilities no chat window can offer

| # | Capability | Why only PERCH can do it |
|---|---|---|
| **1** | **Stack context across applications** — select a paragraph in a PDF, then a function in your IDE, then a cell in a spreadsheet, then ask one question about all three | A chat window only receives what you paste. Cross-application context requires OS-level presence |
| **2** | **Answers land in place** (§4.3) | The answer replaces or follows your selection in the app you were already in |
| **3** | **Explicit private mode** (§4.4) | Routes to a fully local model so the content never leaves the machine |
| **4** | **Portable memory** — plain files you can export, edit or delete | The 2026 switching analysis found users now prioritise *"data portability"* |
| **5** | **Works with no internet** | On a plane, in a college lab, on a restricted network. Every cloud assistant is a blank screen |
| **6** | **Any model** — local, free cloud tier, or your own paid key | Model choice is against every vendor's interest, and free for us |

---

# PART III — HOW THE OS INTEGRATION ACTUALLY WORKS

**This section exists because it is the part of the project nobody on the team has built before. Every
mechanism below is a documented Windows API with an existing Rust binding. Nothing here is speculative.**

## 3.1 The three triggers

### T1 — Global hotkey
```
   Win32 RegisterHotKey  →  system-wide, works regardless of which app has focus
   Rust:  tauri-plugin-global-shortcut  (first-party Tauri v2 plugin)
```
The simplest of the three, and the reliable fallback for everything else.

### T2 — Read the current selection *(the hard one, so it has two paths)*

**Path A — UI Automation (preferred, clean):**
```
   IUIAutomation::GetFocusedElement()      → the control the user is typing/reading in
   → GetCurrentPattern(TextPattern)        → if the control exposes text
   → GetSelection()                        → the selected range
   → range.GetText()                       → the actual string
```
Windows UI Automation is *"an accessibility framework... which provides programmatic access to most
user interface elements on the desktop."* It exists so screen readers can do exactly this.
**Rust binding: the `uiautomation` crate** on crates.io (wraps the Windows UIAutomation COM API, with
process, dialog, event and clipboard support), or Microsoft's official `windows` crate.

**Path B — clipboard round-trip (universal fallback):**
```
   1. save the user's current clipboard contents
   2. SendInput  Ctrl+C  to the focused window
   3. read the clipboard  →  this is the selection
   4. restore the user's original clipboard
```
Less elegant, works essentially everywhere — including apps that do not implement TextPattern.

> **Design rule: try Path A, fall back to Path B, and log which one worked per application.**
> That per-app coverage table is a real deliverable — no competitor publishes one.

### T3 — Screenshot
```
   overlay a transparent full-screen window  →  user drags a region
   →  BitBlt / Windows.Graphics.Capture  →  PNG in memory
   →  optional OCR to text
```
Same mechanism every screenshot tool uses.

## 3.2 Placing the panel beside your work

```
   GetForegroundWindow()   → handle of the app the user is in
   GetWindowRect(hwnd)     → its position and size on screen
   → compute a slot to the right (or left, if there is no room)
   → show PERCH's window there, always-on-top, without stealing focus
```

**Tauri v2 supports this directly** — `alwaysOnTop`, `skipTaskbar`, `transparent`, multi-window and
system tray are configuration flags, not workarounds. Transparency enables non-rectangular shapes and
rounded corners. A published 2026 write-up (*"Why I Chose Tauri v2 for a Desktop Overlay"*) confirms
the pattern, including polling the cursor and toggling `setIgnoreCursorEvents` so the transparent
region stays click-through while the panel itself remains interactive.

**Not stealing focus is the critical detail.** If the panel takes focus, the host application loses its
selection and the whole interaction breaks. The window is created non-activating.

## 3.3 ⭐ Edit in place — how the answer gets back

**This is the capability that separates PERCH from a chat window, so the mechanism matters.**

```
   User selects an awkward sentence in an email  →  triggers PERCH  →  "make this more formal"
   →  answer generated
   →  user presses Enter (or clicks "Replace")

   1. put the answer on the clipboard
   2. restore focus to the original window   (we saved its HWND at trigger time)
   3. SendInput  Ctrl+V                       → the selection is replaced, because it is still selected
   4. restore the user's previous clipboard contents
```

**Why replacement works without any app-specific integration:** in every text editor on Windows, typing
or pasting while text is selected *replaces* that text. We are not writing an Outlook plugin, a Word
plugin, and a VS Code plugin. **We are using the behaviour every text field already has.**

**Three actions, user's choice:**
| Action | Effect |
|---|---|
| **Replace** | overwrite the selection with the answer |
| **Insert after** | leave the original, append below |
| **Copy only** | put it on the clipboard, change nothing |

**Rejected alternative — per-application plugins.** An Office add-in, a VS Code extension, a browser
extension. Better fidelity, but it means N integrations, N review processes, and it only ever works in
the apps we shipped for. **The clipboard path works in everything on day one.**

## 3.4 Feasibility summary — what is proven vs what is work

| Mechanism | Status |
|---|---|
| Global hotkey | ✅ first-party Tauri plugin |
| Foreground window rect / positioning | ✅ basic Win32 |
| Always-on-top, transparent, non-activating panel | ✅ Tauri v2 config |
| Clipboard round-trip for selection | ✅ standard, universal |
| UI Automation selection read | ✅ `uiautomation` crate — **coverage varies by app, which is why Path B exists** |
| Paste-back / replace | ✅ same clipboard mechanism, reversed |
| Region screenshot | ✅ standard |

> **Nothing in Layer 1 requires a driver, a kernel hook, an OS modification, or a special permission.
> It is the same API surface screen readers and RPA tools have used for twenty years.**

---

# PART IV — THE SYSTEM

## 4.1 Four layers

```
   ┌─────────────────────────────────────────────────────────────┐
   │  L1  SURFACE      capture · summon · present · edit in place│
   ├─────────────────────────────────────────────────────────────┤
   │  L2  CONTEXT      assemble the prompt within a token budget │
   ├─────────────────────────────────────────────────────────────┤
   │  L3  MEMORY       store · organise · retrieve what is yours │
   ├─────────────────────────────────────────────────────────────┤
   │  L4  EXECUTION    route to the chosen model · tools · stream│
   └─────────────────────────────────────────────────────────────┘
```

**L2 and L3 are the AI/ML core.** L1 is what the panel sees. L4 is what makes it free.

## 4.2 Two surfaces, one agent

| Surface | When |
|---|---|
| **Slim side panel** | the default. Beside your work, sized not to occlude it, dismissed with Escape |
| **Full window** | normal chat, session history, memory editing, settings. Same agent, same memory |

**A short question never opens a window. A long session gets a proper one.** The panel has an *expand*
control that carries the conversation into the full window unchanged.

**Critical interaction rule:** a selection is **tagged as context, not converted into a command.**
Highlight and Windows "Click to Do" give you a fixed menu — *summarize / translate / explain*.
**PERCH attaches the selection and lets you type any prompt**, including one unrelated to the selection.

## 4.3 Layer 2 — Context assembly *(ML core, part 1)*

**The job:** given a question, a selection, and everything known about the user, decide **what actually
enters the prompt**, under a hard ceiling set by the chosen model.

```
   budget = context_window(model) − reserve(response) − reserve(system)

   Priority order:
     1. system + persona          small, always
     2. the selection             always — it is why the user summoned us
     3. current conversation      recent turns, oldest truncated first
     4. retrieved memory          ← whatever remains
     5. tool results              claimed from (4) when a tool runs
```

**Memory items enter whole or not at all** — half a project description is worse than none.

> **This is what makes model choice possible.** Swap from a local Qwen3 4B to a frontier API and the
> budget recomputes; nothing else changes. The same memory layer serves both.

**Relevance uses three signals:** semantic similarity to the query and selection; **structural match**
(a project block is relevant to a coding question, not to a leave email); and recency/use.

**Rejected alternative — always inject the whole profile.** It burns the budget and produces answers
that awkwardly restate your job title when you asked about a bug.

## 4.4 ⭐ Private mode — declared, never inferred

**You are right that classification is the wrong answer here.** Deciding what is "private" from the
content itself means a classifier with a false-negative cost of *leaking a company secret to a cloud
API*. **No accuracy figure makes that acceptable, and we are not going to pretend otherwise.**

**PERCH does not guess. Privacy is a user-declared policy, in three forms:**

| Mechanism | How it works |
|---|---|
| **1. Per-request toggle** | The panel has a **Private** switch. Flip it, and the request goes to the local model. Visible before you send, on every request |
| **2. Source rules** *(the useful one)* | You declare a **source** private once: *"anything from this application is private"*, *"anything from this folder is private"*, *"anything from this window title pattern is private"*. PERCH knows the source app and document at capture time — **it doesn't need to understand the text, only where it came from.** Deterministic, auditable, no model involved |
| **3. Global default** | Set local as the default and escalate to cloud explicitly. For anyone handling regulated data, this is the only sane setting |

**Where this actually matters:**
- Your employer's codebase — you may be contractually barred from pasting it into a cloud service
- An unpublished thesis or paper under review
- Anything under NDA
- Medical, financial, or legal documents belonging to someone else
- Your own credentials and configuration files

**The demonstrable claim:** in private mode, **zero bytes leave the machine** — provable with a packet
capture, which is a better privacy demonstration than any policy page.

> **Not a hidden classifier. A visible switch and a rule you wrote.** That is defensible to a panel
> and, more importantly, to a user deciding whether to trust it.

## 4.5 Layer 3 — Memory *(ML core, part 2)*

| Kind | Contents | Written by |
|---|---|---|
| **Identity** | who you are, background, how you want answers written | **you** |
| **Domain** | projects, courses, ongoing work — the structured blocks | **you, via extraction prompts** |
| **Episodic** | past conversations and their outcomes | the system |
| **Working** | this session | the system |

```
   Store:     text  +  category  +  embedding  +  timestamps  +  use count
   Index:     local vector index (small local embedding model)
   Retrieve:  category filter → semantic top-k → recency/use rerank → budget-aware selection
   Persist:   SQLite + plain files. No server
```

**Every memory item is a file you can open, edit or delete. Memory you cannot read is memory you
cannot trust** — and after Recall, that is not a slogan.

**Categories beyond projects:** academic (institution, year, formatting conventions), writing style
(tone, length, things you never want written), professional, accessibility constraints, and
**user-defined categories with user-defined schemas** — the extensibility point.

## 4.6 Layer 4 — Execution

**Model registry**, holding for each entry: provider, endpoint, model id, **context window**, tool
support, and whether it is local. Everything upstream reads `context_window` from here.

| Route | Cost |
|---|---|
| **Ollama, local** | free, no rate limit on `localhost:11434` |
| **NVIDIA NIM** | free key, no card, 100+ models, ~40 req/min |
| **Your own API key** | whatever you already pay |

⚠️ **Automatic adaptive routing is explicitly v2.** The user chooses; switching is one click.

**Tools:** web search and fetch (a local 4B model has no idea what happened last month), local file
read, OCR, clipboard write — declared only when the selected model supports tool calling, and charged
against the same budget.

---

# PART V — BUILD

## 5.1 Stack

| Layer | Choice | Why |
|---|---|---|
| Shell | **Tauri v2** | **30–50 MB idle vs Electron's 150–300 MB.** For an always-running background app this decides whether people keep it |
| Core | **Rust** | hotkeys, UI Automation, clipboard, window management, tray |
| UI | React + TypeScript | fast iteration on the surface, which is what gets judged |
| AI/ML | **Python sidecar** | embeddings, retrieval, budget assembly — the ML work, in the language the team knows |
| Storage | SQLite + files | no server, inspectable, portable |
| Local inference | **Ollama** | free, no rate limit |

## 5.2 Team split (5)

| | Owns |
|---|---|
| **S1** | Memory — schema, embeddings, retrieval, extraction prompts |
| **S2** | Context assembly — budget model, relevance, ranking, ablations |
| **S3** | **OS layer** — hotkeys, UIA + clipboard capture, positioning, paste-back |
| **S4** | Interface — panel, full window, sessions, settings, onboarding |
| **S5** | Execution + packaging — model registry, tools, streaming, installer |

## 5.3 Phases

| Phase | Deliverable |
|---|---|
| **0** | **OS-layer proof** — three triggers + positioning + paste-back working *(see `/perch/demo`)* |
| 1 | Trigger → Ollama → answer in the panel |
| 2 | Memory store, embeddings, retrieval, identity block |
| 3 | Budget assembly, model registry, local + cloud |
| 4 | Extraction prompts, project blocks, import flow |
| 5 | Full window, sessions, screenshots, private mode |
| 6 | Benchmarks, ablations, latency and privacy measurement |
| 7 | Installer, docs, release |

---

# PART VI — EVALUATION

| # | What | Against |
|---|---|---|
| **E1** | Memory retrieval quality | **LongMemEval** (500 questions, 6 categories), **LoCoMo** (1,540 questions, up to 35 sessions). Honest framing: near-saturated at 92–94%; we demonstrate competence, we do not claim a record |
| **E2** | **Context assembly ablation** — no memory / full profile always / budget-aware selection, at three model sizes | **Ours.** Nobody publishes this, because nobody else has to serve a 4B local model and a frontier API from one memory layer |
| **E3** | Latency — trigger to first token, local vs cloud | measured |
| **E4** | **Private mode: bytes leaving the machine = 0** | packet capture |
| **E5** | **UI Automation coverage per application** | measured table — no competitor publishes one |

---

# PART VII — RISKS

| Risk | Response |
|---|---|
| *"This is just orchestration"* | **L2 and L3 are real ML** — embeddings, retrieval, ranking, budget optimisation, with benchmarks and an ablation. Lead with memory and context, not the popup |
| Adjacency to NeuroGram / ContextOS | Base paper is a **KDD 2026 personal-assistant benchmark**, not a memory survey. The word *memory* does not appear before the architecture section |
| Highlight has $50M and 500k users | **They pivoted to enterprise in March 2026.** Cloud-only, closed, rate-limited. We are local-capable, open, free, model-agnostic |
| UI Automation coverage gaps | Clipboard fallback covers the rest; coverage documented honestly as a deliverable |
| Antivirus false positives | Sign the installer; keep all capture user-initiated |
| Scope sprawl — *the failure that killed Humane* | **One primitive: bring your context to where you already are.** Adaptive routing, multi-device sync and app automation are all v2, and named as v2 |

> **The first slide:**
> ***You pay for four AI assistants. None of them know you. PERCH is the one that does — and it works
> inside all of them.***
