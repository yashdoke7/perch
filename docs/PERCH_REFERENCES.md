# PERCH — References and Evidence Base

**Working name: PERCH.** *A personal AI that perches beside whatever you are already doing — summoned
by selection or shortcut, aware of who you are, never a window you have to go to.*
*(Name is a placeholder; the metaphor is small, alongside, appears and leaves.)*

> **Status marks:** ✅ verified against a primary source · 🟡 secondary source · ⚠️ not yet read.
> **Nothing marked ⚠️ is quotable to a panel.**

---

# PART 1 — THE BASE PAPER

> **Framing decision.** An earlier draft used the ACM TOIS memory survey as the base paper. **That was
> wrong for this panel** — it announces the project as *memory architecture*, which is what NeuroGram
> (A13) and ContextOS (B9) are, and invites a collision on the first slide. **The base paper must say
> *personal AI assistant*.** Memory is then visibly one component of an assistant, not the subject.

### ✅ PRIMARY — "PAUSE: A User-Centric Benchmark for Personal AI Assistants in Unified Service Environments"
**ACM SIGKDD 2026 (KDD '26), 9–13 August 2026, Jeju Island.** arXiv 2607.27354

**Why this is the base paper:**

1. **ACM, 2026** — meets the panel's requirement exactly.
2. **Its subject is literally "personal AI assistants."** No interpretation needed, no collision with a
   memory-architecture project.
3. **Its definition is our specification.** A personal AI assistant must *"reason over persistent user
   state, respect user-specific configurations and permissions, and sustain long-horizon,
   constraint-aware interactions."* **"Persistent user state" is our memory layer, named as an
   assistant capability rather than as an architecture.**
4. **It evaluates three dimensions** — stateful reasoning, multi-service coordination, user-coupled
   interaction — the first and third of which are exactly what PERCH is built around.

**And it hands us the gap, quantified:**

> ### *"State-of-the-art proprietary models fail to reach **70% task completion** on scenarios requiring **stateful reasoning and configuration awareness**."*

**That is an ACM 2026 measurement that today's assistants fail at knowing and using who you are.** It is
the single most useful sentence in our evidence base: the problem is not the model, it is the state
around it — which is the entire thesis of this project.

**Where it stops, and therefore where we begin:** PAUSE is a **benchmark**. It measures assistants in
*unified service environments* — assumed to already have access and configuration. It does not build a
system, does not address how a user supplies their own state, does not address OS-level capture, and
does not address operating within a fixed token budget across heterogeneous local and cloud models.

### ✅ CONCEPTUAL ANCHOR — "Personal LLM Agents: Insights and Survey about the Capability, Efficiency and Security"
Li et al., **Institute for AI Industry Research (AIR), Tsinghua University.** arXiv 2401.05459

The definitive taxonomy for this exact product category: agents *"deeply integrated with personal data
and personal devices and used for personal assistance."* Its three challenge areas map onto our four
layers almost one-to-one:

| Its category | Its sub-challenges | Our layer |
|---|---|---|
| **Fundamental capabilities** | task execution, **context sensing**, **memorization** | L1 Surface, L3 Memory |
| **Efficiency** | inference, customization, **memory manipulation** | L2 Context, L4 Execution |
| **Security & privacy** | confidentiality, integrity, reliability | local-first design |

⚠️ **arXiv-only, so it is not the base paper** — but it is the paper whose vocabulary we use throughout,
and the one that proves "personal LLM agent" is an established research category rather than a product
idea we invented.

### ✅ SUPPORTING — personalization
**"From Generic Intelligence to Personalized AI: A Tutorial on Foundations of LLM Personalization"** —
**ACM SIGKDD 2026**, 10 August 2026. Wang, Zeng, Wang, Wang, Sun, Li, Yu (Beihang, Nankai, BUPT, UIC).
Six parts: introduction, personalized prompting, personalized adaptation, personalized alignment, data
foundations and evaluation, future directions. Covers *"user preferences, interaction histories,
profiles, and contextual signals"* via retrieval-augmented generation, prompting, representation
learning and RLHF.

**Note honestly:** it does **not** treat memory systems, persistent profiles, context assembly or
assistant architectures as distinct topics. **That absence is useful to us** — it is a 2026 ACM tutorial
on personalization that does not cover how you actually assemble a personalized context under a budget.

### ✅ SUPPORTING — memory, now correctly demoted to a component reference
| Paper | Venue | What we take |
|---|---|---|
| **A Survey on the Memory Mechanism of LLM-based Agents** | **ACM TOIS Vol 43(6), 2025**, DOI 10.1145/3748302 | the formal definition and taxonomy of a memory module. **Cited for L3 only** |
| **Bridging Intuitive Associations and Deliberate Recall: Empowering LLM Personal Assistant with Graph-Structured Long-term Memory** | **Findings of ACL 2025** | dual-path recall — fast associative lookup plus deliberate search |
| **Memory in the LLM Era: Modular Architectures and Strategies in a Unified Framework** | **VLDB 2026** | modular decomposition we adapt |
| From Human Memory to AI Memory | arXiv 2504.15965 | episodic/semantic/procedural split |
| ⚠️ **AdaMem** | arXiv 2606.21144 | write-side selection — what is worth storing at all |
| ⚠️ **Mnemonic Sovereignty** survey | arXiv 2604.16548 | memory ownership; supports local-first |

> **How to present this to the panel, in one line:** *"Our base paper is a KDD 2026 benchmark for
> personal AI assistants, which found that even frontier models fall below 70% when a task requires
> knowing the user's state. We build the assistant that fixes that, on the desktop."*

---

# PART 2 — WHY PERSONAL AI PRODUCTS HAVE FAILED, AND WHAT IT TELLS US

**This is the most useful evidence in the document, because the failures are recent, expensive, and
publicly analysed — and every stated cause is one our design avoids by construction.**

| Product | Outcome |
|---|---|
| **Humane AI Pin** | Raised **$230M**, shipped **fewer than 10,000 units**, sold to HP for **$116M** |
| **Rabbit R1** | Sold **100,000 units**, then **mass returns**; company pivoted |
| **Rewind AI** | Acquired by Meta (as Limitless). **Mac app shut down 19 Dec 2025**; EU/UK access cut immediately |
| **Microsoft Recall** | Internally considered a failure; audits found an admin-rights attacker could exfiltrate the database. Microsoft is **cutting back Copilot across Windows** after user backlash (Jan–Feb 2026) |

**The published causes:**

1. **Non-functional at launch** — the Pin's assistant was slow and unreliable; the R1's "Large Action Model" barely worked.
2. **Hardware constraints that software cannot fix** — the Pin overheated, the R1 died in four hours.
3. **Solving too many problems** — the Pin promised to replace phone, watch, assistant and camera, and *"failed at everything."*
4. **Building a separate thing instead of improving existing tools** — *"they could have leveraged the power of existing smartphones."*

> ### The stated lesson, verbatim:
> ### ***"AI doesn't need a new gadget — it needs to improve the tools you already use."***

**And the Microsoft failures add a fifth cause:** users did not object to capability, they objected to
**forced integration** and **always-on capture**. The complaint was incoherence — *"Microsoft has
ingredients in Copilot, Windows Search, File Explorer, Recall, Edge, PowerToys, and Phone Link, but
the meal still arrives as separate plates."*

**How PERCH is designed against each:**

| Failure cause | Our design decision |
|---|---|
| New hardware | **No hardware.** Software only, existing laptop |
| Too many problems | **One primitive**: bring an AI to the thing you are already looking at |
| Separate destination | **No destination** — it appears where you are |
| Always-on capture | **Summoned only.** Nothing is read unless you invoke it |
| Forced integration | **Opt-in by definition** — a shortcut you press |
| Incoherence | **One surface, one memory, one place to configure** |

---

# PART 3 — COMPETITORS, VERIFIED INDIVIDUALLY

## 3.1 Highlight AI — the closest competitor ✅

| | |
|---|---|
| **Funding** | **$50M total** — $10M seed (2024), **$40M Series A March 2026** led by Khosla Ventures (General Catalyst, Valor Equity, SV Angel, Makers Fund) |
| **Users** | **500,000+**, including employees at Google and DoorDash |
| **Origin** | 2024 spinoff from Medal (a game-clip recorder). New CEO appointed March 2026 |
| **Platforms** | Mac and Windows, free tier |

**What it does:** select on-screen text to summarize, translate or analyze; talk, type or screenshot;
grounds responses in current screen activity; local audio transcription; voice control of apps;
integrations with GitHub, Notion, Slack, Google Calendar.

**✅ THE CRITICAL FINDING — they left this segment.** With the Series A they repositioned as
*"the Shared Intelligence Layer for the Agentic Age of Work"* — an **"intelligent operating system for
teams and AI agents."** Their headline capabilities are now **meeting preparation, attendee insights,
decision summaries and team intelligence.**

> **The incumbent executed a B2C → B2B pivot in March 2026. The individual user is no longer their
> product.**

**Weaknesses to compete on:**
- **Cloud-dependent**, and now rate-limited — their own framing: *"frontier models cost money... no app can give them away for free forever."*
- **No model choice.** You use what they route to.
- Reported uninstall problems — leftover processes and startup errors.
- **Closed source.**

## 3.2 Microsoft — building it, but gated and retreating ✅
**Windows 11 "Click to Do"** performs AI actions on selected screen content — the same primitive.
**But it requires a Copilot+ PC**, i.e. a dedicated NPU. Most laptops, and the overwhelming majority in
India, do not have one. And Microsoft is actively **dialling back** its Windows AI push after backlash.

## 3.3 The Mac-only wall ✅
| Tool | Cost | Platform |
|---|---|---|
| Raycast AI | $8/month | **Mac** |
| Apple Intelligence | free, built in | **Mac / iOS** |
| Dottie | free, open source | **Mac** |
| BoltAI | $79 one-time | **Mac** |

**The entire "best AI assistant" review category is a Mac category.** Windows is served by Highlight
(now enterprise-focused) and Microsoft (hardware-gated).

## 3.4 Local-first tools — right philosophy, wrong shape ✅
| Tool | Local? | OS-integrated? |
|---|---|---|
| **Jan.ai** — 5.3M downloads | ✅ | ❌ **an app window you open** |
| AnythingLLM | ✅ | ❌ |
| Khoj — self-hostable second brain | ✅ | ❌ |
| PyGPT — Win/Mac/Linux, context history | ✅ | ❌ |
| Chatbox — local via Ollama | ✅ | ❌ |
| Open Cowork, LIYA Neural OS, PyWinAssistant | ✅ | partial |

> **Every one of these is a destination.** You leave what you are doing and go to them. **That is the
> exact behaviour PERCH exists to remove.**

## 3.5 The positioning table — the empty row

| | Windows | No special hardware | Local option | Cloud choice | Selection-triggered | Individual user | Open source |
|---|---|---|---|---|---|---|---|
| Highlight AI | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ **pivoted** | ❌ |
| Click to Do | ✅ | ❌ **NPU** | ✅ | ❌ | ✅ | ✅ | ❌ |
| Raycast / Apple | ❌ | — | partial | partial | ✅ | ✅ | ❌ |
| Jan.ai / PyGPT / Khoj | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| **PERCH** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

# PART 4 — MEMORY: THE STATE OF THE ART WE BUILD ON

## 4.1 Existing frameworks ✅
| Framework | Approach |
|---|---|
| **Mem0** | extracts structured facts, stores in a vector DB, retrieves by semantic similarity. **Layers memory by scope** — conversation, session, user, organisation — and **promotes facts between layers** |
| **Zep** | builds a **temporal knowledge graph**; combines graph traversal with vector search. Best for time-aware queries |
| **Letta (MemGPT)** | in-context **core memory** always present + **archival memory** retrieved on demand |
| **LangMem, Supermemory** | memory primitives |

**Published performance:** modern retrieval stacks reach **~7,000 tokens per retrieval at >91% recall**
on LoCoMo-style long-horizon benchmarks, versus **25,000–100,000+ tokens** for full-context approaches.
Reported gains: **26% on LoCoMo**, **20–30% on LongMemEval** over naive RAG or full-context.

**What we take:** Mem0's scope layering and promotion. **What we do not claim:** inventing memory.

## 4.2 Benchmarks ✅ — the component evaluation we can actually run

| Benchmark | Contents |
|---|---|
| **LongMemEval** | **500 questions, 6 categories** — single-session user recall, single-session assistant recall, single-session preference recall, knowledge update, temporal reasoning, multi-session recall. Tests five abilities: extraction, multi-session reasoning, temporal reasoning, knowledge updates, **abstention**. Settings at **115K tokens** (S) and up to **1.5M** (M) |
| **LoCoMo** | **1,540 questions, 4 categories** — single-hop, multi-hop, open-domain, temporal. ~**300 turns**, ~9K tokens, up to **35 sessions** per conversation |
| **PersonaMem, PerLTQA, DialSim, BEAM** | personalised memory — explicit facts and implicit preferences |

**2026 reference scores: LoCoMo 92.5%, LongMemEval 94.4%, BEAM-1M 62%.**

> ⚠️ **Important framing:** LoCoMo and LongMemEval are near-saturated. **We do not pitch beating them.**
> We use them to *validate* that our memory layer is competent, and we report honestly. The
> practitioner consensus is that *"no single evaluation fully characterizes production memory
> performance."* **BEAM-1M at 62% is the honest headroom.**

⚠️ **To read:** LongMemEval-V2 (arXiv 2605.12493) and StreamMemBench (arXiv 2606.14571) — both target
newer, harder settings.

---

# PART 5 — MODEL ECONOMICS: WHY THIS IS BUILDABLE AND CHEAP NOW

## 5.1 Local models crossed the line in 2026 ✅
| Model | Footprint | Quality |
|---|---|---|
| **Qwen3 4B** | **~3 GB** (Q4) | practical on any laptop |
| **Qwen3 8B** | **~5.2–6 GB** (Q4) | fits 8 GB RAM comfortably |
| Llama 3.3 8B | — | **73% MMLU** |
| Qwen3 14B | — | **83% MMLU, 85% HumanEval** |
| Phi-4 (14B) | — | strongest small open-weight in its class |

> *"Small quantized models are now genuinely capable for personal assistant tasks like note
> organization, coding help, and general writing."* **This was not true in 2024. It is what makes the
> local option real rather than a compromise.**

## 5.2 The cost floor is effectively zero ✅
| Route | Terms |
|---|---|
| **Ollama, local** | free, open source, **no rate limit on localhost:11434** |
| **NVIDIA NIM** | free API key with the Developer Program, **no credit card**, ~1,000 credits, **100+ models** (DeepSeek, Llama, Qwen, Mistral, Nemotron). Practical community baseline **~40 requests/minute** |
| **OpenRouter BYOK** | bring your own provider key; **free up to $25,000/month of list-price inference**, then 5% |

> **A student can run PERCH for ₹0 — fully local, or on NIM's free tier, or with their own key. That is
> the pricing story, and it is the one thing a $50M-funded competitor structurally cannot match.**

---

# PART 6 — BUILD STACK, VERIFIED

## 6.1 Tauri v2 over Electron ✅ — and this matters more than usual

| | **Tauri v2** | Electron |
|---|---|---|
| Installer | **< 10 MB** | > 100 MB |
| **Idle RAM** | **30–50 MB** | **150–300 MB** |
| Gap | **~25× smaller bundle, 50–75% less memory** | |

Real migration: **Hoppscotch went 165 MB → 8 MB with a 70% memory reduction.**
Guidance for 2026: *"start a new app in Tauri v2 unless you have a specific reason not to."*

> **PERCH is always running.** A background assistant that idles at 250 MB is a background assistant
> users uninstall. **30–50 MB is the difference between a tool people keep and one they don't.** This
> is a product decision, not a taste decision.

## 6.2 OS integration ✅
**Microsoft UI Automation** is the documented Windows accessibility framework providing *"programmatic
access to most user interface elements on the desktop"*, exposing `IUIAutomationElement` per element.
It exists precisely so assistive tools can read other applications. **This is the supported path — not
a hack.** Global hotkeys, clipboard access and screen capture are all standard Win32.

**No legal barrier.** Documented, permissioned APIs, used by screen readers and RPA tools.
**Practical frictions:** screen-reading apps can trip antivirus heuristics, and any capture behaviour
must be visibly user-initiated to avoid the Recall backlash.

---

# PART 7 — WHAT WE CLAIM AND WHAT WE DO NOT

| We do **not** claim | Why |
|---|---|
| Inventing selection-triggered AI | Highlight and Click to Do exist |
| Inventing agent memory | Mem0, Zep, Letta are mature |
| Beating LoCoMo / LongMemEval | Near-saturated at 92–94% |
| A novel retrieval algorithm | Not needed, not credible |

| We **do** claim |
|---|
| **The first open-source, model-agnostic, OS-integrated personal assistant that runs fully local on ordinary hardware** — the empty row in §3.5 |
| **User-authored memory** — structured personal context the user writes and owns, routed by relevance, not silently extracted from conversation |
| **Token-budget-aware context assembly** that adapts to whichever model is selected, so the same memory layer works from a 4B local model to a frontier API |
| **An honest component evaluation** on public memory benchmarks, plus latency and privacy measurements nobody publishes for a real assistant workload |

---

# PART 8 — READING QUEUE

1. ⚠️ **Base paper full text** — ACM TOIS 10.1145/3748302. Extract its taxonomy verbatim; our architecture must speak its vocabulary
2. ⚠️ **ACL 2025 graph-structured personal assistant memory** — closest prior work to our retrieval design
3. ⚠️ **AdaMem** (2606.21144) — write-side selection
4. ⚠️ **LongMemEval-V2** (2605.12493) and **StreamMemBench** (2606.14571) — are these runnable by us?
5. ⚠️ **Mnemonic Sovereignty survey** (2604.16548) — supports the local-first argument
6. ⚠️ **Confirm Highlight's pivot** from their own site/blog, not press coverage — it is load-bearing for §3.1
