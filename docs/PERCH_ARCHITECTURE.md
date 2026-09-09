# PERCH — Architecture (final)

> **PERCH is your own AI. It runs in the background of your desktop, it knows who you are, and it
> works inside whatever application you are already in.**
>
> You keep your other subscriptions for what they are individually good at. **PERCH is the one that
> holds the memory** — including the memory you pull back out of those other tools — and it is the one
> that does the everyday, generalised work: drafting, rewriting, explaining, answering, summarising,
> looking things up, filling things in, wherever you are on the machine.

**Companions:**
[PERCH_REFERENCES.md](PERCH_REFERENCES.md) — every paper, link and claim.
[PERCH_OS_PRIMER.md](PERCH_OS_PRIMER.md) — how the OS layer works, from basics, and how OS + app + AI wire together.

---

## Document map

| Part | Contents |
|---|---|
| **I** | Why this exists — and the one honest thing that changed after the literature check |
| **II** | What the user actually gets, across all memory classes |
| **III** | The memory model — six classes, open tags, storage format |
| **IV** | ★ Retrieval: router, ranker, admission scorer, budget packer |
| **V** | The OS surface — triggers, panel, edit in place |
| **VI** | Tools — the full agentic surface |
| **VII** | Execution — model routing, private mode |
| **VIII** | ★ The complete pipeline, wired end to end |
| **IX** | Build — stack, phases, team |
| **X** | Evaluation |
| **XI** | ★ Self-critique — the weakest points, stated before anyone else finds them |
| **XII** | Risks |

---

# PART I — WHY THIS EXISTS

## 1.1 The problem: your context is trapped per-vendor

**Nobody uses one AI any more.** A typical user has ChatGPT for general questions and career advice,
Claude Code or Copilot for programming, Perplexity for research, Gemini inside Docs.

**Each one holds a separate, private memory of you, and none of them can see the others.**

| Fact | |
|---|---|
| ChatGPT's assistant market share fell from ~60% (early 2025) to under 45% (Q1 2026) | people move constantly |
| A power user pays **$70–110/month** across four assistants | fragmentation is expensive |
| Users lose **15–30 minutes** of context per platform switch | fragmentation is slow |
| Frontier models fall **below 70% task completion** when a task needs stateful reasoning about the user | **PAUSE, ACM SIGKDD 2026** |

**The concrete version:** your college details and career context are in ChatGPT. Your final-year
project — stack, bugs, decisions, timeline — is in Claude Code across dozens of sessions. Neither can
see the other, so **you do the merge manually, in your head, every time.**

## 1.2 The thesis — corrected

An earlier draft of this document said PERCH's adoption move was *"we emit a context block you paste
into ChatGPT."*

> **That was wrong, and it defeats the purpose.** If the answer is "paste our block into their window,"
> the user is still starting from scratch somewhere else, and PERCH is a clipboard utility.

**The corrected thesis:**

> ### PERCH is the assistant that is yours. It absorbs the memory stranded in the others, and it does the general work — everywhere on your machine, in the background, without you going anywhere.

You may still use Claude Code for a deep refactor or Perplexity for a literature sweep. **That is fine
and expected** — those tools are better at those specific jobs. But:

- **the memory lives in PERCH**, not in whichever window you happened to type it into
- **the everyday work happens in PERCH**, because PERCH is already there, in the app you are in
- **when you deliberately want to continue a specific thread elsewhere**, PERCH can hand that tool a
  briefing. This is an escape hatch for a named situation — **it is not the product's reason to exist**,
  and it is not on the first slide.

## 1.3 What you actually wanted, and why it cannot be built

> *"If there was a way dynamically, where all the AI agents through authentication and authorization of
> one account could get memory of all the applications…"*

**That is the correct design, and it will never ship.** There is no cross-vendor memory API, and there
will not be one:

1. **Memory is the moat.** It is the switching cost. OpenAI's memory of you is precisely what stops you
   leaving. A vendor exposing it via API is funding its own churn.
2. **No standard exists.** There is no OAuth-style "read my assistant memory" scope anywhere.
3. **Liability.** Assistant memory contains health, financial and employment content. No vendor exports
   it to a third-party binary on request.

**So the bridge has to be something the vendors already ship for another reason. It is: the data export.**

## 1.4 ★ Yes — this *can* use your existing subscriptions, in one specific way

You asked me to check. The honest split:

| | Possible? |
|---|---|
| Route PERCH's model calls **through** your ChatGPT Plus / Claude Pro subscription | **No.** Subscriptions cover the vendor's own client only. API access is separately billed with a separate key. There is no supported path, and unsupported ones violate ToS |
| Pull **your conversation history** out of those subscriptions | **Yes — officially, on every major platform** |

**Verified export paths (this is a feature of the subscription you already pay for):**

| Platform | Route | Format |
|---|---|---|
| **ChatGPT** | Settings → Data Controls → Export data → emailed ZIP | `conversations.json` |
| **Claude** | Settings → Privacy → request data export → emailed archive | JSON |
| **Gemini** | `takeout.google.com` → deselect all → select Gemini → emailed archive | JSON / HTML |

> **This is the mechanism.** Your subscription's export button is the legitimate, supported,
> ToS-compliant bridge between a vendor's memory of you and your own. PERCH parses those archives
> **locally**, extracts typed memory from them (§3), and from then on **that knowledge is yours** —
> outside the tool that captured it, usable by whichever model you choose.

**And it is a one-way valve in the right direction.** Everything flows into the thing you own.

## 1.5 Why no incumbent builds this — and the two that came closest

**A neutral personal context layer is against every model vendor's business model.** OpenAI wants you
in ChatGPT, Google in Gemini, Microsoft in Copilot, Apple on a Mac.

**Microsoft is the real objection, so state it first and honestly.** At Build 2026 Microsoft announced
the **Windows AI Platform**: a Copilot Runtime, an AI Orchestrator, and a **Windows Semantic Index** —
*"a personal semantic index encrypted with Windows Hello biometrics, enabling persistent agent memory
and context"* — over a **Windows Agent Runtime**.

> **That is our Layer 3, being built into the operating system. Pretending otherwise would be fatal in
> a review.**

**What it actually means for us — four things, all verifiable:**

1. **It validates the architecture.** The OS vendor concluded that a personal semantic index with
   persistent agent memory is the right shape. We are not arguing for an odd idea.
2. **It is not shipped.** Copilot Runtime targets GA with **Windows 11 26H2**. Initial rollout targets
   **24H2 Enterprise/Pro**, requiring VBS and SLAT. **Windows 11 Home is not the target.**
3. **No third-party access is documented.** The Semantic Index serves Microsoft's own services. You
   cannot point your own agent, or your own model, at it.
4. **Microsoft's consumer AI record is a retreat.** They killed Copilot features and merged the Copilot
   apps in **August 2026**; Recall was judged a failure after audits showed an admin-rights attacker
   could exfiltrate the database. Nadella on the earlier hardware gating: *"We made a mistake by tying
   the AI narrative to a hardware spec."*

> **So: Microsoft is building a closed, edition-gated, unshipped, vendor-locked version of Layer 3 with
> no model choice. We are building an open, portable, model-agnostic one that runs on Home edition
> today.** That is a defensible position. "Nobody is doing this" is not, and is also false.

**The other near-competitor left.** Highlight AI raised **$40M Series A in March 2026** (Khosla-led,
CEO Sergei Sorokin, ex-Discord) to build *"the shared intelligence layer for the agentic age of work"* —
an intelligent OS **for teams**, unifying activity across enterprise tools. Their stated product
direction is now team and enterprise intelligence.

⚠️ **Precision, because the panel will push:** I can verify the funding, the leadership and the stated
enterprise repositioning. **I cannot verify that the individual-user product was discontinued** — so we
say *"repositioned toward teams,"* not *"abandoned consumers."* Do not overstate this on a slide.

---

# PART II — WHAT THE USER ACTUALLY GETS

## 2.1 The one-sentence product

> **Select anything, anywhere in Windows. Press a key. Ask. The answer comes back knowing who you are —
> and lands in the document you were already in.**

## 2.2 Worked examples, one per memory class

You said the earlier examples were all "resume and application filling" — a thin application of AI, and
all inside one class. **Here is one per class, with the reason PERCH beats opening another AI.**

### Identity — the class that is always on

**Situation.** You are writing anything at all: an email, a comment, a message to a professor.

**Without PERCH.** Every assistant needs to be told, every session, that you are a final-year
Computer Engineering student at a Pune college, that you write plainly and hate padding, that you want
British spelling, that you never want an answer to open with "Certainly!".

**With PERCH.** It is stored once. It is small enough to be in every prompt regardless of budget. The
first draft is already in your voice.

> **Why not just use ChatGPT's memory?** Because it is ChatGPT's. It does not apply when you are in
> Claude, or in your IDE, or offline on a train.

### Academic — the class that makes coursework tractable

**Situation.** You are reading a paper PDF for a Deep Learning unit. You select a dense paragraph on
batch normalisation and ask *"how does this connect to what we did in the optimisation unit?"*

**Without PERCH.** The assistant does not know your syllabus, your semester, which topics your
department actually covered, or your exam format. You describe all of it first — and again next week.

**With PERCH.** Academic memory holds your institution, semester, subject list, unit breakdown and
submission conventions, imported once. The answer is anchored to **your** course, not to a generic one.

> **Why better:** the context is reusable across every paper you will read this semester, and it works
> in the PDF reader, not in a browser tab you have to switch to.

### Project — the class with the richest structure

**Situation.** A stack trace in your IDE. Select it, ask *"why is this happening?"*

**Without PERCH.** Paste the trace into a chat window, re-explain the architecture, re-explain which
library versions you pinned and why, and hope you remember that you hit something similar in March.

**With PERCH.** Project memory holds the stack, the architecture decisions **and the reason each was
chosen**, the problems already solved and how, and the timeline. It can tell you *"this is the same
async-context problem you hit on 14 March; you fixed it by moving the initialisation into the worker."*

> **Why better:** the coding assistant that knew this has it buried in a session it will not surface.
> PERCH imported it and can retrieve it by meaning.

### Career — the class that spans years

**Situation.** A recruiter emails. You are in the reply window.

**Without PERCH.** Open an assistant, re-describe your projects, your skills, the roles you want, the
tone you use with recruiters.

**With PERCH.** Trigger in the compose window. Career memory supplies target roles and skills, Project
memory supplies what you actually built, Identity supplies the tone. **Three classes, one draft, in the
window you were already in.**

### Health — the class that proves private mode matters

**Situation.** A prescription changes. You want to prepare questions before the next appointment.

**Without PERCH.** You would have to paste your medical history into a cloud assistant. Most people
reasonably will not.

**With PERCH.** Health memory is **private by default** (§7.3), so the request is answered by the local
model and **zero bytes leave the machine.** It knows your conditions, current medications and known
allergies, so it can flag an interaction worth asking about.

> **Why better:** this is not a "better answer" argument, it is a *"this is the only version of this
> that is acceptable to run at all"* argument. No cloud assistant can offer it.

### Personal — the class that handles ordinary life

**Situation.** Planning a trip with two friends. You select the itinerary draft and ask it to fix the
budget split.

**Without PERCH.** Re-explain who is coming, dietary constraints, the budget ceiling, who paid last time.

**With PERCH.** Personal memory has it. **This is the class that makes PERCH a daily habit rather than a
study tool** — and habit is what makes the other classes worth building.

### ★ The cross-class case — the one no other AI can do

**Situation.** Writing a statement of purpose for a postgraduate application.

**This single task needs Identity (voice, background) + Academic (institution, coursework, grades) +
Project (what you built and why it was hard) + Career (what you want next).**

> **No other assistant has all four, because no other assistant is allowed to.** ChatGPT has some of it,
> Claude Code has a different part, and neither will give it to the other. **PERCH is the only place
> those four can sit in one index — and the routing to combine them is Part IV.**

## 2.3 What PERCH is, functionally

It is a **general-purpose agent**, not a text-rewriter with a memory bolt-on. It has the full tool
surface of a modern agent (Part VI): web search and fetch, file and document reading, OCR, code
execution, memory operations, application control. **The memory and the OS surface are what make it
yours; the tools are what make it useful.**

---

# PART III — THE MEMORY MODEL

## 3.1 Design rule: few classes, many tags

You warned that too many categories jumble things. **You are right, and there is a principled reason.**

> **A class is a routing decision. Every class you add is another chance for the router to be wrong —
> and router error is the exact failure we are trying to eliminate.** Fine distinctions therefore belong
> in *tags*, which only refine ranking **inside** an already-chosen class and cannot cause a routing miss.

| | Classes | Tags |
|---|---|---|
| Set | **closed — six** | open, user- and extractor-generated |
| Purpose | routing + privacy + admission floors | ranking refinement within a class |
| Cost of error | **high** — wrong class means wrong context or none | low — a bad tag slightly reorders results |

## 3.2 The six classes

| Class | Holds | Default sensitivity |
|---|---|---|
| **Identity** | name, role, institution, languages, writing voice, standing instructions | normal |
| **Project** | bounded work: purpose, stack, architecture decisions + rationale, problems + fixes, timeline, results, open items | normal |
| **Academic** | institution, semester, subjects, unit breakdown, formats, deadlines, grading conventions | normal |
| **Career** | roles held, skills, applications, interviews, targets, employer constraints | normal |
| **Health** | conditions, medications, allergies, appointments, reports | **private** |
| **Personal** | relationships, preferences, finances, travel, home, commitments | **private** |

**Plus two system stores, not user classes:**

| Store | Written by | Purpose |
|---|---|---|
| **Episodic** | the system | past PERCH conversations and their outcomes |
| **Working** | the system | the current session only |

**Why exactly these six.** They partition by *how the knowledge is used and how sensitive it is*, which
is what routing and privacy need — not by subject matter, which is what tags are for. Splitting
Academic into "courses / exams / labs" would add three routing errors and zero retrieval benefit,
because within Academic the ranker already separates them.

## 3.3 The item schema

Every memory item is **one Markdown file with YAML frontmatter.**

```markdown
---
id: prj-perch-0007
class: project
title: PERCH selection capture falls back to clipboard
tags: [perch, windows, uiautomation, clipboard, os-layer]
entities: [PERCH, UI Automation, Win32]
sensitivity: normal
source: {kind: import, platform: claude, session: 2026-08-14, confidence: 0.9}
created: 2026-08-14
updated: 2026-08-16
uses: 4
---

UI Automation cannot read the selection in every application — Electron apps and some
custom controls do not implement TextPattern. The fallback is a clipboard round-trip:
save the clipboard, send Ctrl+C, read, restore. Decided 14 Aug 2026 after testing.
```

**Why Markdown + frontmatter, and not a database row or a bare vector store:**

| Requirement | Why this format |
|---|---|
| *"Memory you cannot read is memory you cannot trust"* | it is a text file. Open it, edit it, delete it |
| Portability — the thing users now optimise for | a folder you can zip, sync or `git init` |
| Retrieval | frontmatter gives **exact filters** (class, tags, dates); the body gives **semantic** matching |
| Scale | the vector index is a **derived artefact** in SQLite. Delete it and it rebuilds. The files are the truth |

**Retrieval unit = one item = one file.** A project is not one enormous file: each decision, problem or
result is its own item, linked by shared tags. **This is what keeps items small enough to enter a prompt
whole** (§4.5).

## 3.4 Write-side gating — how we keep memory from bloating

> *"We can't overload the memory as well to scale it."*

**Correct, and this is a named open problem, not a detail.** *Personalize-then-Store* (KAIST, 2026)
shows universal static storage policies waste the memory budget on transient interactions while losing
what matters, and proposes **session-level storage gating**. They also report honestly that accurate
gating *remains an open challenge*.

**Our policy — three rules, deliberately conservative:**

1. **Nothing is stored silently from ordinary chat.** Identity, Project, Academic, Career, Health and
   Personal items are created by **import** or **explicit user action**. Episodic is separate and capped.
2. **On import, extraction is gated.** The extractor proposes items; **the user reviews and accepts** in
   a single screen. Rejected items are not stored.
3. **Near-duplicates merge, they do not accumulate.** On write, if cosine similarity to an existing item
   in the same class exceeds 0.92, PERCH proposes an **update** to that item rather than a new one.

**Caps, enforced:** per-class item ceilings, Episodic capped by age and count, and a *"never stored"*
list the user controls. **Memory growth is bounded by design, not by hope.**

## 3.5 Import — the three paths

| Path | When | How |
|---|---|---|
| **1. Platform export** ★ | primary. You have history in ChatGPT / Claude / Gemini | drop the export archive in. PERCH parses it **locally**, segments sessions, runs class-typed extraction, and presents proposed items for review |
| **2. Live** | as you use PERCH | you tell it something and mark it worth keeping |
| **3. Extraction prompt** | one specific session, or a platform with no export | paste a class-specific prompt into that session; paste the structured block back |

### The extraction prompts — one general contract, six class schemas

You asked whether it should be one prompt or many. **Both, in a specific arrangement:**

> **One prompt *contract* — a fixed output format that the importer can parse — with a per-class
> *schema* selected by the user before extraction.**

One prompt is too vague: ask "extract what matters about me" and you get prose that cannot be typed,
tagged or gated. Six unrelated prompts is unmaintainable and produces six incompatible formats.

**The contract (identical for all six):** return a YAML list of items, each with `class`, `title`,
`tags`, `body`, `confidence`, and nothing else. **The schema (per class)** tells it what fields the
body must cover:

| Class | The body must cover |
|---|---|
| **Identity** | role, institution, languages, stated writing preferences, standing instructions |
| **Project** | purpose · stack and versions · architecture decisions **and the reason for each** · problems hit **and how each was resolved** · timeline · results and numbers · open items |
| **Academic** | institution · semester · subjects and units · assessment format · conventions · deadlines |
| **Career** | roles · skills · applications and their outcomes · interview experiences · targets |
| **Health** | conditions · medications and dosages · allergies · appointments · reports |
| **Personal** | people and relationships · preferences and constraints · commitments · finances · travel |

**The user picks the class before importing**, which is what makes the item typed rather than guessed —
and typing at the source is what makes admission auditable in §4.4.

### ★ How it is actually built (`app/ingest/`)

```
   exports.py   archive  ->  Session objects          per-platform, fails loudly
   extract.py   Session  ->  Proposal objects         one class per run, model-driven
   review.py    Proposal ->  MemoryStore              only what a human accepted
```

**Four decisions worth stating, because each one is a place this could have gone wrong:**

| Decision | Why |
|---|---|
| **The class is pinned by us, not read from the model's reply** | The prompt tells it to emit `class:`, but the importer *overrides* that with the class the user chose, and surfaces any disagreement as a review warning. The class is the privacy boundary (§7.3) — a bad extraction filing a health fact under Academic would route it to a cloud model. **The model may not choose the privacy label.** |
| **The contract is parsed by hand, not with PyYAML** | Models produce almost-YAML: a stray fence, a "Here are the items:" preamble, an indent that slips. PyYAML answers every one of those with a single exception that loses the **entire batch**, including the nine items it parsed perfectly. A tolerant parser for our own fixed contract fails **per item** and keeps the rest — the isolated, loud failure §11.5 asks for. It also keeps the dependency list honest; `schema.py` hand-rolls frontmatter for the same reason. |
| **Long sessions split at turn boundaries** | Cutting mid-turn extracts items from half a sentence, which then read as confident, incomplete facts — the same failure the packer's whole-items-only rule exists to prevent. |
| **An unreachable model raises, it does not return `[]`** | "Your history contained nothing worth keeping" and "nothing was running" are opposite messages, and the second must never be delivered as the first. Extraction is the one component that genuinely cannot be stubbed. |

**The review surface is a terminal triage loop**, one item at a time, shown in full: `y` accepts, Enter
rejects, `e` retitles, `a`/`d` bulk-apply to the rest, `q` ends. Two properties are deliberate — **the
default is no**, because a `y`-default over hundreds of items produces a memory full of things nobody
read; and **the write happens in one pass after review ends**, so an interrupted session cannot leave
memory in a state the user never saw summarised.

> **A tkinter review screen is a wrapper over this same accept/reject core, not a rewrite of it.** The
> triage logic takes its I/O as arguments precisely so it is testable headlessly and reusable behind a
> GUI later.

---

# PART IV — ★ RETRIEVAL: ROUTER, RANKER, ADMISSION SCORER, PACKER

**This is the technical core, and it is built around the failure you identified.**

## 4.1 The failure you described, named properly

> *"If it's medical related but there was nothing related to medical in the memory — just a mention of
> a medical college — it shouldn't just add up college details. It should see what in medical."*

**You independently identified a problem the 2026 literature has named and measured.**

- **Cross-domain leakage** — *Beyond Similarity: Trustworthy Memory Search for Personal AI Agents*
  (2026) defines exactly this: a memory unit *"satisfies the semantic ranking criteria but violates
  contextual admissibility."* Their measured leakage rate before mitigation: **27.0%**.
- **Over-personalisation / irrelevance** — **OP-Bench** (2026) measures *"injecting personal references
  when queries don't warrant personalization"* and finds systems **retrieve at ~80% similarity even in
  deliberately baited cases**, attend to memory tokens **2× more than to the user's own query**, and
  that memory-augmented methods score **26.2–61.1% worse** than memory-free baselines on this axis.

> **The single most important number in our evidence base:** naive memory injection makes an assistant
> *worse*, by up to 61%, than having no memory at all. **Retrieval that does not know when to stay quiet
> is a liability, not a feature.**

**Honest prior art, stated up front:** MemGate solves this with a *learned* query-conditioned neural
gate over frozen embeddings. CRAG uses a retrieval evaluator with a relevance threshold and corrective
action. Self-RAG trains reflection tokens to decide when to retrieve at all. **We did not invent
gating and will not claim to.** §4.6 states precisely what is ours.

## 4.2 The pipeline

```
   question + selection + source app
        │
   (1)  INTENT          what is being asked, in what domain, at what scope
        │
   (2)  CLASS ROUTER    which of the six classes are even eligible
        │
   (3)  RETRIEVE        over-fetch top-N per eligible class (semantic + tag filter)
        │
   (4)  RANKER          order candidates by usefulness to THIS question
        │
   (5)  ADMISSION       ★ absolute floor per class + margin test  →  or admit nothing
        │
   (6)  PACKER          whole items, priority order, until the budget is spent
        │
   (7)  DECLARE         every injected item is listed in the panel
```

## 4.3 Steps 1–4: route, retrieve, rank

**(1) Intent.** A small, cheap step: classify the request into a **domain** (which classes could
plausibly help) and a **scope** (does this need memory at all?). *"Rewrite this sentence to be shorter"*
needs Identity for voice and nothing else. **A large fraction of requests need almost no memory, and
recognising that early is most of the win.**

**(2) Class router.** Produces an eligibility set, not a single class. Multi-class is normal — the SOP
example needs four. Routing uses the intent, the **source application** (a `.py` file in an IDE raises
Project; a PDF in a course folder raises Academic), and tag overlap.

**(3) Retrieval.** Within eligible classes only: exact frontmatter filters first, then semantic top-N
with deliberate over-fetch (N ≈ 30), because the ranker and the gate need candidates to reject.

**(4) Ranker.** Orders candidates by usefulness to this specific question. Signals:

| Signal | What it contributes |
|---|---|
| Semantic similarity to question **and** selection | the base |
| **Tag overlap** with the resolved intent | the refinement your class/tag split enables |
| Entity match | "PERCH", "DPDP Act", a person's name |
| Recency and use count | recent, repeatedly useful items rank higher |
| Class prior | Identity is cheap and near-always useful; Personal rarely helps a stack trace |

> **The ranker's output is an ORDER. An order says nothing about whether the best item is any good.**
> That is the whole point of step 5, and it is the step most systems skip.

## 4.4 ★ Step 5 — the admission scorer

**The principle, in one line:**

> ### Ranking is relative. Injection must be absolute.

**The mechanism:**

```
   for each eligible class c:
       s_max(c) = score of the best candidate in c

       if s_max(c) < τ_c :
            class c contributes NOTHING            ← not "the best of a bad lot"
       else:
            admit items where  s ≥ τ_c   AND   s ≥ α · s_max(c)
                                └ absolute floor    └ margin test, kills the long tail

   if no class is admitted:
       ABSTAIN — answer from general knowledge, and say so in the panel
```

**Two thresholds, two different jobs:**

- **τ_c — the absolute floor, per class.** Calibrated per class because classes differ in how tightly
  they cluster. Health items are specific and cluster tightly, so τ is high. Identity is broad and
  should be admitted easily, so τ is low.
- **α — the margin.** Even inside an admitted class, an item scoring far below that class's best is
  filler. Filler is what burns budget and causes the 2× memory-attention distortion OP-Bench measured.

**Your medical example, traced:**

| Step | What happens |
|---|---|
| Intent | domain = health, scope = needs memory |
| Router | Health eligible; Academic weakly eligible on the token "medical" |
| Retrieve | Health returns nothing. Academic returns *"B.E. Computer Engineering, PES Modern College"* |
| Ranker | that Academic item is now **rank 1** — it is the best of what exists |
| **Admission** | its score is **below τ_academic for a health-domain query**. **Academic contributes nothing** |
| Result | **abstain.** PERCH answers from general medical knowledge and states: *"no stored health context matched."* |

> **A naive system injects the college. Ours says it has nothing — and saying so is the correct answer.**

**Abstention is measurable, not a slogan.** LongMemEval tests abstention as one of its five abilities,
and OP-Bench's irrelevance category measures precisely the injection this prevents. **We can put a
number on it.**

## 4.5 Step 6 — the budget packer

```
   budget = context_window(model) − reserve(response) − reserve(system) − reserve(tools)

   fill order:
     1. system + Identity          small, always
     2. the selection              always — it is why the user summoned us
     3. recent conversation        oldest turns truncated first
     4. admitted memory            ← in ranker order, into whatever remains
     5. tool results               claimed from the same allowance when a tool runs
```

**Items enter whole or not at all.** Half a project decision is worse than none — it reads as a
confident, incomplete fact.

> **This is what makes model choice real.** Swap Qwen3 4B for a frontier API and the budget recomputes.
> Nothing else in the system changes. **The same memory layer serves a 3 GB local model and a 200K-token
> frontier model — that is the point, and it is Contribution 1.**

**Why this is not a solved problem:** the 2026 survey *Externalization in LLM Agents* states that the
context window *"remains the scarcest shared resource"*, with memory, skills, tool schemas and reasoning
traces all competing for one finite budget — *"a harness-level coordination problem."* **It names the
problem. It does not solve it for the local-to-frontier span.**

### ★ 4.5a The live ledger — where C1 is actually implemented

Reserving space for tool *schemas* before generation is the easy half. The half that matters is what
happens when a tool **returns**: a result arriving mid-loop must be paid for out of the same allowance
the packer already spent.

> **This was documented before it was true.** `client.py`'s own docstring said *"each tool result
> re-enters the budget"* while the code appended `result[:4000]` and hoped. Measured: four tool steps
> against an 8192-token local model overflow the window by **~2320 tokens**. The model then truncates
> from the far end — which is exactly where the system prompt and the memory live — so the visible
> symptom is *the model ignoring its instructions*, and nothing points at the budget.

**What happens now, per tool result, in `Packed.make_room()` and `_charge_tool_result()`:**

| | |
|---|---|
| **it fits** | charge it against `used`, nothing else changes |
| **it does not fit** | **evict the lowest-ranked admitted memory** until it does — bottom of the ranker's order first, because that is the item the ranker already called least useful — then **re-render the prompt** and push it back into the live message list |
| **it still does not fit** | truncate the result, and **say so inside the text**, so the model knows it is reasoning from a fragment rather than assuming it has the whole thing |
| **there is no room at all** | omit the result entirely, and tell the model **not to invent the contents** |

**Identity is never evicted.** Not a special case bolted on — it is the same decision the fill order
above already makes when it puts *system + Identity* first and calls it *small, always*. A web search
result that costs you your own voice is a bad trade at any size, and identity items are small enough
that protecting them frees almost nothing anyway.

> **Every eviction is reported**, through the same provenance path as every other drop. A tool result
> that costs you a memory is a trade PERCH made on your behalf without asking, so the panel says which
> items went and why — the auditability argument in §4.6 applies to eviction exactly as it does to
> admission.

**This is the difference between having a budget and coordinating one.** Any system can cap a prompt.
C1's claim is that memory and tools draw on a single allowance whose size comes from
`context_window` alone — so the same layer serves a 4B local model and a frontier API, and the
*only* thing that changes is a number in the registry.

## 4.6 What is genuinely ours — stated precisely

| | |
|---|---|
| **We do not claim** | inventing memory gating (**MemGate**), relevance thresholds (**CRAG**), retrieve-or-not decisions (**Self-RAG**), agent memory (**Mem0, Zep, Letta**), or OS-level personal indexes (**Microsoft's Windows Semantic Index**) |
| **C1 — budget-aware assembly across heterogeneous models** | the same memory layer serving a 4B local model and a frontier API, with an ablation at three model sizes. Named as an open coordination problem by the 2026 survey; unsolved for this span |
| **C2 — *declarative* admission on a user-owned type system** | MemGate's gate is **learned** from embeddings and cannot explain a rejection. Ours is **typed at the source** — the class is assigned at import, the floor is per class, and every drop is auditable. **The same type system also drives privacy routing (§7.3)** — one primitive, two jobs |
| **C3 — import from official platform exports** | the only ToS-legitimate cross-vendor bridge, with class-typed extraction and human review |
| **C4 — the OS surface** | not a research claim; it is the product, and it is already built (§5, Phase 0) |

> **C2's defensible sentence:** *a learned gate cannot tell you why it dropped your memory; a typed floor
> can, and a personal agent has to be able to.*

---

# PART V — THE OS SURFACE

**Full detail, from basics, is in [PERCH_OS_PRIMER.md](PERCH_OS_PRIMER.md).** Summary here.

## 5.1 Three triggers

| | Mechanism |
|---|---|
| **T1 — hotkey** | Win32 `RegisterHotKey` + message loop. System-wide, focus-independent |
| **T2 — selection** | **Path A:** UI Automation — `GetFocusedElement` → `TextPattern` → `GetSelection` → `GetText`. **Path B:** clipboard round-trip — save, `Ctrl+C`, read, restore. Try A, fall back to B, **log which worked per app** |
| **T3 — region** | transparent full-screen overlay → drag → capture → optional OCR |

## 5.2 One surface, two sizes

You are right that this should not be framed as two products.

> **The panel is the product.** It is where PERCH lives: beside your work, sized not to occlude it,
> dismissed with Escape. **A short question never opens a window.**
>
> **The full view is the same panel, expanded** — for long sessions, history and memory editing. Same
> agent, same memory, same conversation, carried over unchanged. It is a *size*, not a *destination*.

**Placement:** `GetForegroundWindow` → `GetWindowRect` → dock right, else left, else screen edge.
Always-on-top, **non-activating** — if the panel steals focus, the host loses the selection and the
whole interaction breaks.

**Interaction rule:** a selection is **tagged as context, not converted into a command.** Highlight and
Click to Do give a fixed menu (summarise / translate / explain). **PERCH attaches the selection and lets
you type any prompt**, including one unrelated to it.

## 5.3 Edit in place

```
   1. put the answer on the clipboard
   2. restore focus to the original window   (HWND saved at trigger time)
   3. SendInput Ctrl+V   → the selection is replaced, because it is still selected
   4. restore the user's previous clipboard
```

**Why no per-app plugin is needed:** in every Windows text field, pasting while text is selected
*replaces* it. Actions: **Replace · Insert after · Copy only**. If Windows refuses the focus change we
**do not paste** — landing in the wrong window is worse than not pasting.

---

# PART VI — TOOLS

**You asked for the full agentic surface. Here it is.** Tools are declared to the model only when it
supports tool calling, and every schema is charged against the same budget as memory (§4.5).

| Group | Tools |
|---|---|
| **Knowledge** | `web_search` · `web_fetch` — mandatory, because a local 4B model has no idea what happened last month |
| **Memory** | `memory_search` · `memory_write` · `memory_update` · `memory_forget` · `memory_list_classes` |
| **Files** | `file_read` · `file_write` · `dir_list` · `file_search` — scoped to user-declared roots only |
| **Documents** | `doc_parse` (PDF / DOCX / XLSX / PPTX → text) · `ocr_image` |
| **Screen & OS** | `capture_region` · `read_selection` · `active_window` · `clipboard_read` · `clipboard_write` · `paste_into` |
| **Applications** | `open_path` · `open_url` · `focus_window` |
| **Compute** | `run_python` — a separate interpreter in isolated mode (`-I`), 10s timeout, for arithmetic, dates, data munging. ⚠️ **Not a sandbox** — see below |
| **Vision** | `describe_image` — when a vision-capable model is selected |
| **Deferred to v2, named as such** | calendar read, email read, shell execution, app automation |

**Tool safety policy — three rules:**

1. **Read is free; write asks.** Anything that changes state outside PERCH (`file_write`, `paste_into`,
   `open_url`) or runs arbitrary code (`run_python`) shows what it will do and waits.
   **Enforced in one place** — `tools/registry.py:dispatch()` — and **deny-by-default**: a caller that
   supplies no approval callback cannot invoke a confirming tool at all. So the headless paths
   (`python -m app ask`, the tests) get read-only tools unless they opt in, and the panel is what
   supplies the prompt.
2. **Every tool call is logged**, visible in the panel, and attributable to a request.
3. **Private mode restricts the tool set.** `web_search` and `web_fetch` are disabled — a tool call is
   an exfiltration path, and a private-mode guarantee that leaks through a search query is worthless.

> ⚠️ **`run_python` is not sandboxed, and an earlier version of this document said it was.** `-I`
> (isolated mode) only stops the *environment* from hijacking the snippet — it ignores `PYTHONPATH`,
> `PYTHON*` variables and the user site directory. The snippet still runs with PERCH's own privileges:
> it can read and write any file the user can, open sockets, and start other programs. The 10-second
> timeout bounds how long it runs, not what it may do.
>
> **So the confirmation is the containment**, which is why `run_python` is `confirm=True` and a human
> reads the code before it executes. A real sandbox — dropped privileges, no network namespace, a
> read-only filesystem view — is the correct fix and is **open work, not something to claim with a flag.**
> Note also that `run_python` is a non-network tool, so it stays *declared* in private mode; a snippet
> that opened a socket would defeat the private-mode guarantee, and only the human read prevents that.

---

# PART VII — EXECUTION

## 7.1 Model registry

Each entry: provider · endpoint · model id · **context window** · tool support · vision support · local
flag. **Everything upstream reads `context_window` from here** — that single field is what makes Layer 2
model-agnostic.

## 7.2 Routes

| Route | Cost |
|---|---|
| **Ollama, local** | free, no rate limit on `localhost:11434`. Qwen3 4B ≈ 3 GB, Qwen3 8B ≈ 5–6 GB (Q4) |
| **NVIDIA NIM** | free key, no card, 100+ models, ~40 req/min |
| **Your own key / OpenRouter BYOK** | whatever you already pay |

⚠️ **Automatic adaptive routing is v2.** The user chooses; switching is one click.

**Where that click is:**

| Surface | |
|---|---|
| **Panel** | a `route: auto / local / cloud` control beside the Private switch, cycling on click. In private mode it reads **`route: local (forced)`** and cycling is inert — the registry enforces local regardless, so showing anything else would be a lie about where the request is going |
| **CLI** | `python -m app ask --route local "…"`, plus `--private` |
| **Default** | `PERCH_ROUTE=local\|cloud\|auto` |
| **Inspect** | `python -m app models` lists what this machine can actually reach, with context windows and capabilities, and names the route a request would take right now |

> `auto` is **local-then-cloud**, not adaptive selection. Naming it `auto` rather than `smart` keeps
> the promise the size it actually is.

## 7.3 Private mode — declared, never inferred

**Content classification is the wrong answer here.** A classifier whose false negative leaks a company
secret to a cloud API is unacceptable at any accuracy figure.

| Mechanism | How |
|---|---|
| **1. Per-request toggle** | a **Private** switch on the panel, visible before you send |
| **2. Source rules** ★ | declare a source private once: *this application*, *this folder*, *this window-title pattern*. **PERCH knows the source at capture time — it never needs to understand the text, only where it came from.** Deterministic, auditable, no model |
| **3. Global default** | local by default, escalate to cloud explicitly |

**Plus a fourth, free from Part III:** **the Health and Personal classes are private by default.** The
type system already knows which memory is sensitive, so **any request that admits a Health or Personal
item is forced local automatically** — with the panel saying why.

> **In private mode, zero bytes leave the machine — provable with a packet capture.**

---

# PART VIII — ★ THE COMPLETE PIPELINE

**One request, end to end, with every component named.**

```
 ┌─ L1  SURFACE ──────────────────────────────────────────────────────────────┐
 │  hotkey (RegisterHotKey)                                                   │
 │      → snapshot host window   GetForegroundWindow + GetWindowRect + HWND   │
 │      → capture selection      UIA TextPattern  ▸ fallback clipboard        │
 │      → panel opens beside the host, non-activating                         │
 │      → user types the question                                             │
 └────────────────────────────────────────────────────────────────────────────┘
                │  question · selection · source app · document path
                ▼
 ┌─ L2  CONTEXT ──────────────────────────────────────────────────────────────┐
 │  intent      → domain + scope + "does this need memory at all?"            │
 │  privacy     → source rules · toggle · global default        ──────────┐   │
 │  class route → eligible classes                                        │   │
 └────────────────────────────────────────────────────────────────────────│───┘
                │                                                         │
                ▼                                                         │
 ┌─ L3  MEMORY ───────────────────────────────────────────────────────────│───┐
 │  filter (frontmatter: class, tags, dates)                              │   │
 │      → semantic top-N over-fetch (SQLite + vector index)               │   │
 │      → RANKER      similarity · tags · entities · recency · class prior│   │
 │      → ADMISSION   τ_c floor + α margin  →  admitted set, or nothing   │   │
 │      → if a Health/Personal item is admitted ─── force local ──────────┘   │
 └────────────────────────────────────────────────────────────────────────────┘
                │  admitted items (possibly empty → abstain)
                ▼
 ┌─ L2  PACKER ───────────────────────────────────────────────────────────────┐
 │  budget = ctx(model) − response − system − tool schemas                    │
 │  fill: system+Identity ▸ selection ▸ conversation ▸ memory ▸ tool results   │
 │  whole items only                                                          │
 └────────────────────────────────────────────────────────────────────────────┘
                │  assembled prompt
                ▼
 ┌─ L4  EXECUTION ────────────────────────────────────────────────────────────┐
 │  registry → route  (local ▸ free tier ▸ own key;  private ⇒ always local)   │
 │  stream ⇄ tool loop  (web · files · docs · OCR · python · memory · OS)      │
 └────────────────────────────────────────────────────────────────────────────┘
                │  answer + provenance + tool log
                ▼
 ┌─ L1  RETURN ───────────────────────────────────────────────────────────────┐
 │  panel shows: answer · which memory items were used · which were dropped   │
 │               and why · which model answered · private or not              │
 │  Replace ▸ Insert after ▸ Copy   → clipboard → refocus HWND → Ctrl+V        │
 │  Episodic write (capped)  ·  memory proposal only if the user asks         │
 └────────────────────────────────────────────────────────────────────────────┘
```

**The two loops that make it an agent, not a template:**

- **Tool loop** (L4): model → tool call → result → model, until it stops. Each result re-enters the
  budget, and the packer may evict low-ranked memory to make room. **Tools and memory compete for one
  budget — that is exactly the coordination problem C1 addresses.**
- **Memory loop** (L3): `memory_search` is *also* a tool. If the packer admitted nothing but the model
  decides it needs something, it can ask — with the admission gate still applied.

---

# PART IX — BUILD

## 9.1 Stack

| Layer | Choice | Why |
|---|---|---|
| Shell | **Tauri v2** | 30–50 MB idle vs Electron's 150–300 MB; installer <10 MB vs >100 MB. PERCH is always running |
| Core | **Rust** | hotkeys, UI Automation, clipboard, window management, tray |
| UI | React + TypeScript | fast iteration on the surface |
| AI/ML | **Python sidecar** | embeddings, ranker, admission, packer — the ML work |
| Store | **SQLite + Markdown files** | files are the truth; SQLite holds the derived index |
| Vector | sqlite-vec | no server, no extra process |
| Local inference | **Ollama** | free, no rate limit |

## 9.2 Phases

| Phase | Deliverable | Status |
|---|---|---|
| **0** | OS-layer proof — three triggers, positioning, paste-back | **done** |
| **1** | **Working prototype**: OS layer + panel + model routing + typed memory + ranker/admission/packer + tool loop + streaming + live stage tracker | **done — 34 tests** |
| **1a** | Panel chrome: drag, resize, persisted geometry, provenance chips | **done** |
| **2** | **Import**: export parsers, class-typed extraction, CLI review triage | **done — 15 tests** |
| **3** | **Execution**: live budget ledger (tool results evict memory), registry, route choice in panel + CLI, private mode | **done — 14 tests** |
| **4** | Screenshots reach the model (vision, with honest refusal when unsupported); multi-turn follow-ups | **partial — 10 tests.** Full view and OCR not started |
| **5** | **Evaluation harness**: E2, E4, E5, E6 runnable offline; E1/E3/E7 reported as unrun with reasons | **partial — 14 tests.** E2/E4/E5/E6 verified against a live Ollama; E1/E3 need external datasets, E7 needs a human |
| 6 | Tauri port, installer, docs, release | |

## 9.3 Team split (5)

| | Owns |
|---|---|
| **S1** | Memory — classes, schema, embeddings, store, import parsers, extraction |
| **S2** | **Retrieval — router, ranker, admission scorer, packer, ablations** |
| **S3** | OS layer — hotkeys, UIA + clipboard, positioning, paste-back |
| **S4** | Interface — panel, full view, provenance display, settings, onboarding |
| **S5** | Execution — registry, tools, streaming, sandbox, packaging |

---

# PART X — EVALUATION

| # | What | Against |
|---|---|---|
| **E1** | **Over-personalisation — the headline** | **OP-Bench** (1,700 instances, 20 users; irrelevance / repetition / sycophancy). Baselines: no memory, naive top-k, ours. **Naive memory scores 26.2–61.1% worse than no memory — we must beat both** |
| **E2** | **Budget-assembly ablation (C1)** | ours. No memory / full profile always / budget-aware, at **three model sizes**. The margin should be largest on the smallest model |
| **E3** | Retrieval quality | **LongMemEval** (500 q, 6 categories, incl. **abstention**) and **LoCoMo** (1,540 q). Honest: near-saturated at 92–94%; we validate competence, we do not claim a record |
| **E4** | Admission gate ablation (C2) | cross-domain leakage rate with the gate off / threshold only / typed floor + margin. **MemGate reports 27.0% → 3.5% as the reference** |
| **E5** | Privacy | bytes leaving the machine in private mode = **0**, by packet capture |
| **E6** | Latency | trigger → first token, local vs cloud |
| **E7** | **UIA coverage per application** | measured table across common Windows apps. No competitor publishes one |

## 10.1 ★ What actually runs — `python -m app eval`

**Four of the seven run on any machine with this repository and nothing else. Three do not.**

```
E1  over-personalisation     needs OP-Bench             NOT RUNNABLE HERE
E2  budget assembly (C1)     needs nothing              ★ runs
E3  retrieval quality        needs LongMemEval/LoCoMo   NOT RUNNABLE HERE
E4  admission gate (C2)      needs a real embedder      runs when one is live
E5  privacy: zero egress     needs nothing              ★ runs
E6  latency                  stages: nothing            ★ runs (generation half needs a model)
E7  UIA coverage             needs a human at a desktop NOT RUNNABLE HERE
```

**The harness prints all seven every time**, with the three that did not run marked and explained.
A harness that prints only what it managed to run teaches the reader that the list is complete —
and the gap between *"we did not measure this"* and *"we measured this and it was fine"* is the
entire difference between an evaluation and a claim. This is the same principle the gate applies to
memory and the ablation applies to its own scorecard.

> ⚠️ **On E1 specifically:** the *26.2–61.1% worse than no memory* figure in the table above is
> **OP-Bench's measurement of other systems**, not ours of PERCH. It is our motivation. Until E1
> actually runs it must never be presented as a PERCH result, and the harness says so in place of
> a number.

### E2's result, and the half of it that fails

Running E2 on the **seed** memory gives a two-part answer, and the part that fails is worth more:

| | Finding |
|---|---|
| **Assembly alone** | **Does not separate the sizes.** The seed profile is ~1,700 tokens over 18 items, which fits a 4K window comfortably. So on this memory the packer is *not yet load-bearing* — and claiming otherwise would be overclaiming |
| **With tools** | **Separates sharply.** After four tool calls, appending blindly overflows the 4K window by **~3,400 tokens** while the live ledger fits, paying with evicted items it reports |

> **The honest form of C1, corrected by its own experiment:** *the packer earns its place when memory
> and tools contend for one allowance — not merely because memory is large.* That is exactly the
> coordination problem the 2026 externalization survey names, and it is a sharper claim than the one
> Part X originally made. A real imported history (hundreds of items) is where the assembly half
> starts to bite; the seed is a demo, not a workload.

### ★ What a live run against Ollama actually found

**Everything above ran for the first time against `nomic-embed-text` and `qwen2.5:3b` on 7 Sept 2026.
Four defects surfaced that months of stubbed unit tests had passed straight over** — which is itself
the finding worth recording:

| Found | |
|---|---|
| **`localhost` cost 2 seconds per Ollama call** | Ollama binds IPv4 only; on Windows `localhost` resolves to `::1` first and waits out a timeout before falling back. **2051 ms vs 42 ms via `127.0.0.1`** — a 50× penalty on every embedding and every generation. E6 reported it as 2036 ms of "retrieval latency"; after the fix, 19.5 ms |
| **`import` crashed on a Windows console** | `review.render()` drew its header in U+2500 box-drawing, absent from cp1252 — so `print()` raised `UnicodeEncodeError` *after* a successful extraction, at the moment it had proposals to show |
| **Every seed item existed twice** | 18 rows, 9 unique. A cross-dimension cosine is 0.0, never reaching the 0.92 merge threshold, so re-seeding under a different backend duplicated everything and the twins competed at retrieval. Hence `python -m app dedupe` |
| **The extractor does not calibrate** | `qwen2.5:3b` emitted `confidence: 1` for **all four** items — filling in a required field, not estimating. That silently disabled the review screen's only automatic signal, since the "unsure" warning keys off that number |

**On extraction quality, stated plainly because the review gate depends on it.** The same run produced
confident, well-formatted, *wrong* items: the model wrote that Electron *"is chosen for its client-side
functionality"* when the transcript had the user moving away from it, and that a performance problem
*"has been addressed"* when the user never said so.

> **A 3B extractor invents outcomes.** That is not a reason to abandon the import path — it is the
> reason §3.4 rule 2 exists. Nothing reaches memory without a human reading it, and the review screen
> now says so on the way in.

### E5 is a necessary condition, not the packet capture

E5 instruments `socket.connect` for the duration of a real private-mode request and classifies every
address this process reaches. **It proves no code path inside PERCH's own process opened a remote
connection.** It does *not* prove no bytes left the machine — a subprocess (`run_python` spawns one)
is invisible to it, as is anything a dependency does through a handle opened earlier.

> **So the packet capture remains the claim to make publicly, and remains unrun.** E5 is what catches
> the realistic regression: someone wiring a new tool, or an embedding call to a cloud endpoint, without
> checking the privacy decision first. That second one is easy to miss — the request is private, the
> model is local, and retrieval still quietly posts your query to an embeddings API.

---

# PART XI — ★ SELF-CRITIQUE

**You asked me to be a critic so this is the final version. The weakest points, and what we do
about each.** Items 6 and 7 were found by breaking the system ourselves, after the first five were
written — which is the reason this section is kept open rather than closed at five.

### 1. "Microsoft is shipping the Windows Semantic Index. You are redundant."
**The strongest objection, and it is legitimate.** Response: it is unshipped (26H2), targets
Enterprise/Pro with VBS+SLAT, exposes **no documented third-party access**, offers no model choice, and
comes from a team that killed Copilot features in August 2026. **We run on Home edition, today, on any
model including a local one.** *We do not claim Microsoft isn't doing this — we claim it will not be
open, and open is the whole point.*

### 2. "Your gating contribution is MemGate."
**Partly true and we say so first.** Ours is declarative rather than learned: typed at the source,
auditable, no training, no extra judge call, and the same type system drives privacy. **If the panel
rejects that as insufficient, C1 (budget assembly) is the load-bearing contribution**, and it stands on
its own with a named open problem behind it.

### 3. "This is orchestration, not ML."
**The risk my memory says this panel actually fails people on.** Response: the ranker is a learned
relevance model, the admission scorer is a calibration problem with per-class thresholds fitted on held
out data, and the packer is constrained optimisation.

> ⚠️ **An earlier version of this section then said "and there are four ablations on public
> benchmarks." That was not true when it was written and it is still not true.** §10.1 is the honest
> count: **two ablations run** (E2 budget assembly, E4 admission gate) and both are **on our own
> memory, not on a public benchmark**. The two public-benchmark experiments — E1 on OP-Bench and E3
> on LongMemEval/LoCoMo — **have never been run**, because neither dataset is vendored here.
>
> **This is the objection's strongest version, and the answer is to run E1, not to phrase item 3
> better.** Until then the defensible sentence is *"two ablations, on our own data, with the
> benchmark work identified and not yet done"* — which is weaker, and true.

**Lead with E2 and E4, the two that actually produce numbers. Do not open with the popup.**

### 4. "Six classes is arbitrary."
Honest answer: **it is a design choice, not a derivation.** The defence is that classes are a routing
device and each one is a new failure mode, so the burden is on adding a seventh, not on justifying six.
**And it is testable** — E1 measures whether routing helps or hurts, so if six is wrong the data says so.

### 5. "Import depends on export formats you do not control."
**True.** They are undocumented JSON that can change without notice. Mitigation: parsers are isolated
per platform and fail loudly; the extraction-prompt path (§3.5) works with **no** export at all; and the
review screen means a broken parser produces nothing rather than garbage.

### 6. ⚠️ "Your per-class floors are numbers you tuned by hand."
**The most honest weakness, and we found it ourselves by breaking it.**

The floors in §4.4 are raw cosine values, and **cosine means different things to different embedders**.
Measured here: `nomic-embed-text` scores *completely unrelated* text at **0.35–0.41**, while the hashed
bag-of-words fallback scores the same pairs near **0.10**. A floor tuned against one silently becomes
meaningless against the other — which is exactly what happened when the embedding service stopped and
the system fell back without saying so.

**Two mitigations, and one honest limit:**

1. Scores are **rescaled against a per-backend measured baseline** before being compared to any floor,
   so a floor means the same thing regardless of which embedder is live.
2. The system **reports which backend answered** and warns loudly when it is on the fallback.
3. **The limit:** the fallback's related and unrelated distributions genuinely *overlap* — an unrelated
   pair at 0.178 against a related pair at 0.071 — so no constant can separate them. That is
   representational, not a tuning problem. **The fallback is a stand-in for demonstrating the pipeline,
   never for reporting a number.**

> **Where this goes next:** floors should be *fitted* on held-out labelled data per class, not chosen.
> That turns E4 from an ablation into a calibration result, and it is the most defensible answer to
> "did you just pick these numbers?" — because the honest current answer is *yes, guided by measurement*.

### 7. ⚠️ "Switching embedding backends silently deleted half the memory."

**Found by inspecting the live development store, not by a test — which is the point.**

The index stores whatever vector the backend produced *at write time*: `nomic-embed-text` gives 768
dimensions, the hashed fallback gives 512. `embed.cosine()` returns `0.0` when the lengths differ.
So a store written under Ollama and then queried without it does not degrade — **every affected item
scores exactly zero and becomes unreachable.** Measured on the development machine: **9 of 18 items
were invisible**, and nothing anywhere said so.

**Why it is worse than it sounds.** The symptom is *the gate abstaining*. That is indistinguishable
from the gate working correctly on genuinely irrelevant memory — so the failure disguises itself as
the contribution behaving as designed. It also broke near-duplicate merging (§3.4 rule 3): a
cross-dimension cosine of 0.0 never reaches the 0.92 merge threshold, so re-seeding created a second
copy of the same identity item, which then competed with its own twin at retrieval time.

**What now happens instead:** `MemoryStore.index_health()` compares stored dimensions against the live
backend; mismatched rows are **skipped and counted** rather than scored zero; and both the agent's
startup banner and the first query print a loud `!! STALE INDEX` warning naming the remedy
(`python -m app rebuild`). Three tests cover it.

**The limit, stated honestly:** this *detects* the problem, it does not prevent it. The index should
record the backend and dimension it was built with and rebuild itself on a mismatch, rather than
asking the user to. That is open work.

> **The general lesson, and it applies to every threshold in Part IV:** a defensive guard that returns
> a neutral-looking value on a malformed input converts a configuration error into a silent wrong
> answer. `return 0.0` looked safe and was the whole bug.

---

# PART XII — RISKS

| Risk | Response |
|---|---|
| *"Just orchestration"* | four ablations, two public benchmarks, a calibration problem. Lead with retrieval, not the panel |
| Windows Semantic Index | §11.1 — validates the shape; closed, gated, unshipped, no model choice |
| Highlight has $50M | repositioned to teams March 2026. **Do not claim they abandoned consumers — unverified** |
| OP-Bench shows memory *hurts* | that is our motivation, not our problem. It is why the admission gate exists |
| UIA coverage gaps | clipboard fallback; coverage documented honestly as E7 |
| Export formats change | isolated parsers, loud failures, prompt path as backstop |
| Antivirus false positives | sign the installer; keep all capture user-initiated |
| Scope sprawl — the failure that killed Humane | **one primitive: bring your context to where you already are.** Adaptive routing, sync, shell and app automation are v2, and named as v2 |

> **The first slide:**
> ### ***You pay for four AI assistants. None of them know you, and none of them will tell each other. PERCH is the one that's yours.***
