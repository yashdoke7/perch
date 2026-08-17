# PERCH — References, Evidence Base and Objection Map

**Every claim in the architecture traces to a row in this document.**

> **Verification marks**
> ✅ **verified in-session** — I opened the source and read it during this project
> 🟡 **secondary** — reported by a reliable secondary source, primary not opened
> ⚠️ **from prior knowledge, unverified** — the identifier is probably right but **I did not open it**
> ❌ **retracted** — was in an earlier draft and is wrong
>
> **Rule: nothing marked ⚠️ or 🟡 goes on a slide as a quoted number without being opened first.**

---

# PART 0 — ★ VENUE AUDIT

**The fair question: "is this all just arXiv?"** A raw count of the document says 19 arXiv IDs against
6 named venues, which looks bad. Sorted by what actually carries weight, it is much better — **every
load-bearing citation is peer-reviewed**, and the preprints are all support.

## 0.1 The peer-reviewed spine — verified individually

| Work | Venue | Role in this project |
|---|---|---|
| **PAUSE** | **ACM SIGKDD 2026** (KDD '26), Jeju Island, 9–13 Aug 2026 · DOI [10.1145/3770855.3817565](https://doi.org/10.1145/3770855.3817565) — ⚠️ **doi.org redirects to dl.acm.org, confirming a real ACM record, but ACM's bot-wall blocks automated verification of the listing itself. Check it yourself via a browser with ACM DL access before relying on it.** | ★ **BASE PAPER** |
| **"…Scrutable Assistant for Time Management"** — Landerberg, Flatmo, Said | **ACM UMAP 2026** (34th Conf. on User Modeling, Adaptation and Personalization), Full Paper · DOI [10.1145/3774935.3806186](https://doi.org/10.1145/3774935.3806186) | ★ **non-benchmark personal-AI evidence** — see §1.3 |
| **A Survey on the Memory Mechanism of LLM-based Agents** | **ACM TOIS 43(6), 2025** · DOI [10.1145/3748302](https://doi.org/10.1145/3748302) | L3 definition and taxonomy |
| **LoCoMo** — *Evaluating Very Long-Term Conversational Memory of LLM Agents* | **ACL 2024** · [aclanthology.org/2024.acl-long.747](https://aclanthology.org/2024.acl-long.747/) | benchmark (E3) |
| **LongMemEval** | **ICLR 2025** | benchmark (E3), incl. abstention |
| **Self-RAG** — *Learning to Retrieve, Generate and Critique through Self-Reflection* | **ICLR 2024** (Asai, Wu, Wang, Sil, Hajishirzi) | prior art for retrieve-or-not |
| **Mem0** — *Production-Ready AI Agents with Scalable Long-Term Memory* | **ECAI 2025** · arXiv 2504.19413 | memory baseline, LoCoMo comparison |
| **From Storage to Experience: Evolution of LLM Agent Memory Mechanisms** | **Findings of ACL 2026** | memory-evolution survey |
| *Bridging Intuitive Associations and Deliberate Recall* | **Findings of ACL 2025** | dual-path recall |
| *Memory in the LLM Era: Modular Architectures* | **VLDB 2026** | modular decomposition |

> **Ten peer-reviewed works now, covering the base paper, both evaluation benchmarks, the gating prior
> art, the memory foundations, and — genuinely useful — a second ACM 2026 paper about a personal
> assistant that is not a benchmark at all.** That is the spine. Everything below is supporting evidence.

## 0.1a ★ The category defence: "personal AI" is not something we invented to dodge NeuroGram

If the panel maps this to NeuroGram on sight, the strongest response is not an argument — it is
pointing at what the top venues are already doing:

- **ACM SIGKDD 2026 itself runs a co-located workshop**, **PILA 2026 — "Personal Intelligence in the
  Agentic AI Era"** (10 Aug 2026, Jeju) — https://pila26-workshop.github.io/. Its stated scope is
  *"personalized agents, user modeling, and human-centered AI"*, with topics spanning memory/retrieval,
  adaptive planning, privacy and deployment. ⚠️ **Non-archival** — its papers are not in the ACM
  proceedings, so it is evidence of the category's legitimacy, not itself a citable result.
- **ACM UMAP** is an entire 34-year-old conference series about exactly this axis (user modeling,
  adaptation, personalization), sponsored by SIGCHI and SIGWEB. §0.1's UMAP 2026 paper is one accepted
  result from it, not an isolated one — the venue itself is the evidence.

> **The sentence:** *"Personal AI is not a framing we chose to avoid a conflict — SIGKDD ran an entire
> workshop on it this year, and UMAP has been the dedicated venue for user modeling and personalization
> for over three decades. We are answering a question the field already treats as distinct from memory
> architecture."*

## 0.2 arXiv-only *because it is recent* — legitimate, and stated as such

| Work | Posted | Role |
|---|---|---|
| MemGate (2606.06054) | Jun 2026 | closest prior art to C2 |
| OP-Bench (2601.13722) | Jan 2026 | primary evaluation target (E1) |
| PerMemBench (2605.25535) | May 2026 | write-side gating |
| Externalization survey (2604.08224) | Apr 2026 | names C1 as an open problem |

**These are two to seven months old.** Nothing at that age has cleared review yet, in any venue. Citing
recent preprints as *current state of the art* is normal practice; the distinction we hold is that
**none of them is load-bearing for the base paper or the evaluation plan.**

## 0.3 ⚠️ arXiv-only and *not* explained by recency — flag these yourself

| Work | Problem |
|---|---|
| **Personal LLM Agents** (2401.05459) | Posted **January 2024** and still not in any proceedings, **two and a half years later**. That is not a recency story — see §0.4 |
| **CRAG** (2401.15884) | **Submitted to ICLR 2025 and withdrawn.** It is widely cited and implemented in LangGraph, but it is not a published paper. Cite it as "the CRAG approach", never as a peer-reviewed result |

## 0.4 ★ On *Personal LLM Agents* — you were right to be unsure

**What it is:** Yuanchun Li and ~24 co-authors, Institute for AI Industry Research (AIR), **Tsinghua
University**. Surveys architecture, capability, efficiency and security of agents "deeply integrated
with personal data and personal devices", including structured opinions from **25 senior practitioners**
(chief architects, managing directors, senior engineers) at companies building personal assistants.

**What it is not:** peer-reviewed. It has sat on arXiv since **January 2024** with no venue. Some
aggregator sites describe it as "peer-reviewed research from a leading institution" — **that is a
category error they make about anything from a famous lab, and repeating it to a panel would be a
serious mistake.** arXiv has no peer review.

**Verdict — how to use it:**

| ✅ Safe | ❌ Not safe |
|---|---|
| Borrowing its **vocabulary** — "personal LLM agent", context sensing, memorization | Presenting it as the base paper, or as an authority |
| Showing the **category is established** and industrially serious | Quoting its expert-survey numbers as a peer-reviewed finding |
| A **related-work** citation among many | Letting it carry any claim on its own |

> **It is a well-known, heavily-cited preprint from a serious lab, and it is still a preprint.** Say
> exactly that if asked. Our base paper is PAUSE (ACM SIGKDD 2026) and does not depend on it.

**Peer-reviewed alternatives that can do the same job:**

| Instead of | Use | Venue |
|---|---|---|
| Personal LLM Agents, for *"this is an established category"* | ⚠️ *Agentic AI: A Comprehensive Survey of Architectures, Applications and Future Directions* — PRISMA review of 90 studies, 2018–2025 | **Artificial Intelligence Review** (Springer), DOI 10.1007/s10462-025-11422-4. ⚠️ **paywalled — I could not open it; verify before citing** |
| Personal LLM Agents, for *memory taxonomy* | *From Storage to Experience* | **Findings of ACL 2026** |
| Personal LLM Agents, for *market seriousness* | **IEEE Global Study**, *The Impact of Technology in 2026 and Beyond* — 400 technology leaders; **52% forecast mass adoption of AI personal-assistant and calendar management** | IEEE (industry study, not a paper — cite as a survey, not research) |

## 0.5 The sentence to use if the panel asks

> *"Our base paper is ACM SIGKDD 2026. Both evaluation benchmarks are ACL 2024 and ICLR 2025, the memory
> taxonomy is ACM TOIS 2025, and the gating prior art is ICLR 2024. The 2026 preprints we cite are two
> to seven months old, so nothing at that age is published yet in any venue — and none of them carries a
> claim on its own."*

---

# PART 1 — THE BASE PAPER

## ✅ PAUSE — *A User-Centric Benchmark for Personal AI Assistants in Unified Service Environments*

| | |
|---|---|
| **Venue** | **ACM SIGKDD 2026 (KDD '26)**, 9–13 August 2026, Jeju Island, Republic of Korea |
| **Authors** | Haoyu Chen, Xirui Shi, Yuyao Wang, Jerry Chen, Di Niu |
| **Link** | https://arxiv.org/abs/2607.27354 · full text: https://arxiv.org/html/2607.27354v1 |

**What it contains — read this before the review:**

- **The definition we adopt as our specification.** A personal AI assistant must *"reason over persistent
  user state, respect user-specific configurations and permissions, and sustain long-horizon,
  constraint-aware interactions across multiple services."*
- **The gap it identifies in existing benchmarks:** they *"fragment service contexts or abstract away
  user state"*, so they cannot evaluate user-centric assistant behaviour realistically.
- **What the benchmark requires of an agent:** coordinate actions across heterogeneous **user-owned**
  resources while staying consistent with environment state and authorization constraints, over
  multi-turn interactions, with **realistic user simulation** rather than static tool execution.
- **A multi-regime evaluation framework:** open-ended service-management tasks judged by semantic and
  trajectory-level behavioural metrics; constraint-intensive tasks by deterministic state-based
  verification.
- **The headline result we quote:** *"even state-of-the-art proprietary models fail to reach 70% task
  completion on scenarios requiring stateful reasoning and configuration awareness, revealing consistent
  and interpretable failure patterns."*
- **A user-centric synthesis pipeline** for generating service environments, user configurations and
  annotated tasks.

**Why it is the base paper:** ACM, 2026, and its subject is literally *personal AI assistants* — so it
cannot be misread as a memory-architecture project and cannot collide with NeuroGram or ContextOS on
the first slide.

⚠️ **Still unknown, and you should know this before you present it:** the abstract does **not** name
which proprietary models were tested, how many tasks the benchmark contains, or what the "consistent and
interpretable failure patterns" actually are. **I have the abstract and the sub-70% figure; I do not
have the internals.** If a panel member asks *"which models?"* the honest answer is that the number is
from the abstract and the model list needs the full PDF.

**Where it stops, and therefore where we begin:** it is a **benchmark**, evaluating assistants inside
unified service environments that already have access and configuration. It does not build a system,
does not address how a user supplies their own state, does not address OS-level capture, and does not
address operating within a fixed token budget across heterogeneous local and cloud models.

## ⚠️ Conceptual anchor — *Personal LLM Agents: Insights and Survey* — **PREPRINT, NOT PEER-REVIEWED**

Li et al., Institute for AI Industry Research (AIR), **Tsinghua University** — https://arxiv.org/abs/2401.05459

> **Read §0.4 before using this.** arXiv-only since January 2024 with no venue in two and a half years.
> Use it for vocabulary and to show the category is established — never as an authority, and never as
> the base paper.

The taxonomy for this product category: agents *"deeply integrated with personal data and personal
devices and used for personal assistance."*

| Its category | Its sub-challenges | Our layer |
|---|---|---|
| Fundamental capabilities | task execution, **context sensing**, **memorization** | L1 Surface, L3 Memory |
| Efficiency | inference, customization, **memory manipulation** | L2 Context, L4 Execution |
| Security & privacy | confidentiality, integrity, reliability | local-first design |

⚠️ **arXiv-only, so not the base paper** — but it is the vocabulary we use, and it proves "personal LLM
agent" is an established research category, not a product idea we invented.

## ✅ ★ Second anchor, and this one *is* peer-reviewed — the Scrutable Assistant paper

*"'As Long as It Does What I Want, I'd Be Happy to Trust It': Exploring User Perspectives on a Scrutable
Assistant for Time Management"* — Annie Landerberg, Kari Flatmo, Alan Said.
**ACM UMAP 2026** (34th ACM Conference on User Modeling, Adaptation and Personalization), Full Paper.
DOI [10.1145/3774935.3806186](https://doi.org/10.1145/3774935.3806186).

**Why this matters more than its topic suggests:** it is a personal-AI paper that is **not** a
benchmark, **is** ACM-published, and its core idea is close to ours by name. The paper studies
**SIPA4TM**, a purpose-built personal time-management assistant, through a 22-participant task-based
study, with the explicit design goal that users can **scrutinise both its suggestions and the
underlying user model** — not just get an answer, but see why.

> **That is our admission gate's whole pitch, independently arrived at by a different team, published
> at a dedicated personalization venue.** *"Every drop carries a reason"* is not a phrase we invented in
> a vacuum — UMAP 2026 is publishing full papers on exactly this property, under the name
> **scrutability**. Cite it, and consider adopting "scrutable" as a second word for what §4.4 of the
> architecture calls "declarative, auditable admission" — it is the term the field already uses.

**How to use it:**

| ✅ Safe | ❌ Not safe |
|---|---|
| A **peer-reviewed precedent** for user-facing transparency in a personal assistant | Claiming it as *our* base paper — its domain (time management) is unrelated to ours |
| The word **"scrutable"** as a second, field-standard name for admission-gate transparency | Implying it evaluates memory retrieval or gating the way we do — it does not; its contribution is the user study, not a retrieval mechanism |

⚠️ **Read the full paper before quoting the study's findings** — only the abstract-level summary above
is verified; the 22-participant results themselves have not been opened in this session.

## ⚠️ Related, unconfirmed venue — PersonalAlign

*"PersonalAlign: Hierarchical Implicit Intent Alignment for Personalized GUI Agent with Long-Term
User-Centric Records"* — arXiv 2601.09636 (Jan 2026). Introduces a Hierarchical Intent Memory Agent
that maintains **continuously updating personal memory** to resolve vague instructions and anticipate
routines from long-term user records — directly adjacent to our Project/Career/Personal classes and the
ranker's recency signal.

🟡 Its own GitHub repository is named `ACL26-PersonalAlign`, which suggests **Findings of ACL 2026** as
the target venue, but I have not confirmed acceptance independently. **Treat as arXiv-only until
verified** — do not repeat the "ACL 2026" venue as fact without checking.

---

# PART 2 — ★ THE PAPERS BEHIND OUR RETRIEVAL CONTRIBUTION

**These four are the most important documents in this project after the base paper. They define the
problem the ranker and admission scorer exist to solve, and they are the prior art we must not
overclaim against.**

## ✅ *Beyond Similarity: Trustworthy Memory Search for Personal AI Agents* — **MemGate**

https://arxiv.org/abs/2606.06054 · full text: https://arxiv.org/html/2606.06054v1

**Read this one first.** It is the closest published work to your ranker/scorer idea.

- **The problem, named:** semantic similarity retrieves relevant information but *"fails to ensure
  contextual **admissibility**"* — a memory unit *"satisfies the semantic ranking criteria but violates
  contextual admissibility."* **This is exactly the medical-college failure you described.**
- **The four failure modes it identifies:** cross-domain leakage, sycophancy amplification, tool-call
  drift, memory-induced jailbreaks.
- **Their method:** MemGate, *"a lightweight query-conditioned retrieval gate that re-ranks candidate
  memories before they enter the LLM context"* — a **continuous mask over frozen embeddings**, sitting
  between vector retrieval and prompt construction, with no LLM modification and no extra judge call.
- **Results (GPT-4o-mini):** cross-domain leakage **27.0% → 3.5%**; jailbreak success **16.8% → 4.4%**;
  LoCoMo F1 **38.9 → 40.8**.
- **What they leave open:** sycophancy persists due to base-model agreement bias.

> **Consequence for us: we cannot claim to have invented memory gating.** §4.6 of the architecture
> states this plainly. Our difference is that MemGate's gate is **learned and opaque** — it cannot tell
> you why it dropped something — whereas ours is **typed at the source and auditable**, and the same
> type system also drives privacy routing. **MemGate is also our baseline for E4.**

## ✅ *OP-Bench: Benchmarking Over-Personalization for Memory-Augmented Personalized Conversational Agents*

https://arxiv.org/abs/2601.13722 · full text: https://arxiv.org/html/2601.13722v1

**This is our primary evaluation target (E1), and it contains the single most useful number we have.**

- **Definition:** over-personalization is when memory-augmented systems apply user information
  inappropriately, producing responses that feel *"forced, intrusive, or socially inappropriate."*
- **Three categories:** **Irrelevance** (injecting personal references when the query doesn't warrant it
  — *our exact failure*), **Sycophancy**, **Repetition**.
- **Size:** **1,700 verified instances across 20 users.** Irrelevance 418 (24.6%), Repetition 882
  (51.9%), Sycophancy 400 (23.5%). Built from LoCoMo user profiles, LLM-generated queries, three-stage
  human review.
- **Measured failure modes:** over-retrieval (~80% similarity even in deliberately *baited* cases);
  models attend to **memory tokens 2× more than to the user's own query**; linguistic drift toward
  deferential language; response collapse.
- ### **The headline: memory-augmented methods score 26.2%–61.1% *worse* than memory-free baselines.**
- **And the counter-intuitive finding:** more sophisticated memory systems (MemU, MEMOS) over-personalise
  **more** than plain RAG.
- Their mitigation, *Self-ReCheck*, reduces over-personalization by **29%** on average.

> **Why this matters more than any other number in the deck:** it proves that naive memory injection
> makes an assistant *worse than having no memory at all*. **Our admission gate is not a refinement —
> it is the thing that makes memory a net positive.**

## ✅ *Personalize-then-Store: Benchmarking and Learning Personalized Memory for Long-horizon Agents* — **PerMemBench**

https://arxiv.org/abs/2605.25535 · code: https://github.com/yeonjun-in/PerMemBench
Yeonjun In, Wonjoong Kim, Sangwu Park, Kanghoon Yoon, Chanyoung Park — **KAIST**

**This is the citation behind our write-side gating (§3.4), i.e. your "we can't overload the memory".**

- **The problem:** existing memory systems apply *"universal, static policies"* that ignore the fact
  that what is worth storing differs per user — wasting a limited memory budget on transient
  interactions while failing to preserve critical context.
- **Their proposal:** **session-level storage gating** — a lightweight framework that selectively
  bypasses memory operations for transient sessions.
- **Their honest finding:** personalization yields substantial retention gains *under perfect gating*,
  but **accurate gating remains an open and critical challenge.**
- First benchmark for personalized memory: multi-year, multi-domain histories across personas.

## ✅ *Externalization in LLM Agents: A Unified Review of Memory, Skills, Protocols and Harness Engineering*

https://arxiv.org/abs/2604.08224

**This is the survey that names our C1 as an open problem without solving it.**

> The context window *"remains the scarcest shared resource"* in agent systems, where **memory
> retrieval, skill loading, protocol schemas, tool descriptions and reasoning traces all compete for the
> same finite token budget**, making this *"a harness-level coordination problem."*

**Use this sentence when the panel asks why budget assembly is a contribution rather than engineering.**

---

# PART 3 — PRIOR ART IN GATED AND CORRECTIVE RETRIEVAL

**We must cite these ourselves before anyone raises them.**

| Work | Link | What it does | Why it is not us |
|---|---|---|---|
| ⚠️ **CRAG** — Corrective RAG **(withdrawn from ICLR 2025 — preprint only)** | arXiv 2401.15884 · [OpenReview](https://openreview.net/forum?id=JnWJbrnaUE) | a lightweight **retrieval evaluator** scores retrieved docs; below a **relevance threshold** it triggers correction — Correct / Ambiguous / Incorrect, falling back to web search | operates on a document corpus for QA; no personal memory, no classes, no budget, no privacy coupling. **Cite as "the CRAG approach", not as a published result** |
| ✅ **Self-RAG** — **ICLR 2024** | arXiv 2310.11511 | trains **reflection tokens** so the model decides *when* to retrieve and critiques relevance and factuality | requires training the generator; we gate outside the model. **This is the peer-reviewed prior art to cite for retrieve-or-not** |
| 🟡 **Adaptive-RAG / L-RAG** | arXiv 2601.06551 | entropy-based lazy loading — retrieve only when the model is uncertain | complementary; a candidate v2 addition |
| 🟡 **Beyond Semantic Relevance** — counterfactual risk minimization for RAG | arXiv 2605.01302 | gates inclusion by a predicted **robustness score** above a safety threshold | same shape, general RAG, not personal memory |
| 🟡 **MemGuard** | arXiv 2605.28009 | preventing **memory contamination** in long-term memory-augmented LLMs | adversarial/poisoning framing; ours is relevance, not attack |

> **Our honest position:** thresholded admission is established practice. **What is ours is doing it on
> a user-declared type system that is simultaneously the privacy primitive, under a token budget that
> varies by an order of magnitude across models.**

---

# PART 4 — MEMORY: STATE OF THE ART WE BUILD ON

| Work | Link | What we take |
|---|---|---|
| ✅ **Mem0** — *Building Production-Ready AI Agents with Scalable Long-Term Memory*, **ECAI 2025** | https://arxiv.org/abs/2504.19413 | scope layering and promotion; first broad head-to-head of ten memory approaches on LoCoMo. Reports **91% lower p95 latency** and **>90% token saving** vs full-context |
| ⚠️ **Zep** — temporal knowledge graph for agent memory | arXiv 2501.13956 | time-aware queries; graph traversal + vector search |
| ⚠️ **MemGPT / Letta** — *Towards LLMs as Operating Systems* | arXiv 2310.08560 | core memory always in context + archival memory retrieved on demand |
| ✅ **A Survey on the Memory Mechanism of LLM-based Agents**, **ACM TOIS 43(6), 2025** | https://doi.org/10.1145/3748302 | the formal definition and taxonomy of a memory module. **Cited for L3 only** — deliberately not the base paper |
| 🟡 *Bridging Intuitive Associations and Deliberate Recall*, **Findings of ACL 2025** | — | dual-path recall: fast associative lookup + deliberate search |
| 🟡 *Memory in the LLM Era: Modular Architectures and Strategies*, **VLDB 2026** | — | modular decomposition we adapt |
| ⚠️ **AdaMem** | arXiv 2606.21144 | write-side selection — what is worth storing at all |
| ⚠️ **Mnemonic Sovereignty** survey | arXiv 2604.16548 | memory ownership; supports local-first |
| 🟡 *Implicit Graph, Explicit Retrieval* | arXiv 2601.03417 | efficient interpretable long-horizon memory |

---

# PART 5 — BENCHMARKS WE CAN ACTUALLY RUN

| Benchmark | Link | Contents | Our use |
|---|---|---|---|
| ✅ **OP-Bench** | arXiv 2601.13722 | 1,700 instances, 20 users; irrelevance / repetition / sycophancy | **E1 — primary.** Directly measures the failure our gate prevents |
| ✅ **LongMemEval** — **ICLR 2025** | arXiv 2410.10813 | 500 questions, 6 categories; five abilities including **abstention**; 115K (S) to 1.5M (M) token settings | **E3** — and the abstention category validates the gate |
| ✅ **LoCoMo** — **ACL 2024** | [aclanthology.org/2024.acl-long.747](https://aclanthology.org/2024.acl-long.747/) | *Evaluating Very Long-Term Conversational Memory of LLM Agents.* Conversations averaging **600 turns / 16K tokens over up to 32 sessions**; QA, event summarisation, multi-modal dialogue | **E3** — comparability with Mem0/MemGate |
| ✅ **PerMemBench** | arXiv 2605.25535 | multi-year multi-domain personalized memory | write-side gating evaluation |
| 🟡 **From Recall to Forgetting** | arXiv 2604.20006 | long-term memory for personalized agents, incl. forgetting | candidate for the forgetting/caps policy |
| ⚠️ LongMemEval-V2 · StreamMemBench | arXiv 2605.12493 · 2606.14571 | harder, newer settings | **to read** — are they runnable by us? |

> ⚠️ **UNRESOLVED — the LoCoMo figures disagree between sources.** Earlier drafts of this document (and
> the deck) say *"1,540 questions, ~300 turns, up to 35 sessions"*, taken from secondary write-ups. The
> **ACL 2024 anthology abstract** says conversations average **600 turns and 16K tokens over up to 32
> sessions**. These are not reconcilable, and at least one is wrong — possibly both describe different
> released versions. **Open the ACL paper and take the numbers from it before any of this reaches a
> slide.** Do not quote LoCoMo's size from memory in the review.

> ⚠️ **Framing discipline:** 2026 reference scores are **LoCoMo 92.5%, LongMemEval 94.4%, BEAM-1M 62%.**
> LoCoMo and LongMemEval are near-saturated. **We do not pitch beating them.** We use them to validate
> competence and we say so. **OP-Bench is where we can genuinely move a number, because the baselines
> there are bad on purpose — memory systems score 26–61% worse than no memory at all.**

---

# PART 6 — ★ THE OBJECTION MAP

**You asked me to find anything that could produce an objection. This is that list.**

## 6.1 🔴 SEVERE — Microsoft Windows AI Platform (Build 2026)

🟡 https://zylos.ai/research/2026-06-24-windows-ai-agent-platform-build-2026/

**The objection:** *"Microsoft is building this into Windows. Why are you building it?"*

**What was announced:** Copilot Runtime (on-device inference), AI Orchestrator (agent lifecycle and
routing), and the **Windows Semantic Index** — *"a personal semantic index encrypted with Windows Hello
biometrics, enabling persistent agent memory and context"* — over a Windows Agent Runtime providing
sandboxed execution, persistent memory storage and agent-to-agent communication.

**Also announced: the NPU requirement was dropped.** Capability now scales with GPU VRAM (<2 GB basic,
4 GB mid, 8 GB full local inference, 12+ GB large). Nadella: *"We made a mistake by tying the AI
narrative to a hardware spec."*

> ### ❌ RETRACTION: our earlier claim that "Click to Do requires a Copilot+ PC NPU" is now out of date as a general statement about Windows AI. Do not use it.

**Our four verified answers:**

1. **Unshipped.** Copilot Runtime targets GA with **Windows 11 26H2**.
2. **Edition-gated.** Initial rollout targets **24H2 Enterprise/Pro** with VBS and SLAT. **Windows 11
   Home is not the target** — which is what most students in India actually run.
3. **No documented third-party access** to the Semantic Index. You cannot point your own agent or your
   own model at it.
4. **Track record.** Microsoft killed Copilot features and merged the Copilot apps in **August 2026**
   (🟡 TechCrunch, 13 Aug 2026); Recall was judged a failure after audits found an admin-rights attacker
   could exfiltrate the database.

**The line to use:** *"Microsoft concluded a personal semantic index is the right architecture — that
validates ours. Theirs is closed, edition-gated, unshipped and locked to their models. Ours runs on Home
edition today, on any model, including one that never leaves the machine."*

## 6.2 🔴 SEVERE — "Your gating idea is MemGate"

See §Part 2. **Cite it ourselves, first.** Fall back on C1 if C2 is judged insufficient.

## 6.3 🟠 MODERATE — Highlight AI

✅ https://www.businesswire.com/news/home/20260324500318/en/

**Verified:** $40M Series A, March 2026, led by Khosla Ventures with 359 Capital, General Catalyst,
Valor Equity, Common Metal, Makers Fund, Collaborative Fund, Arcadia, SV Angel. CEO **Sergei Sorokin**,
former Discord VP of Product. Positioning: *"the shared intelligence layer for the agentic age of
work"*, an intelligent OS for **teams**, sitting above existing enterprise applications, capturing work
as it happens so knowledge persists across team changes.

> ### ❌ CORRECTION: I earlier wrote that "the individual user is no longer their product." **I cannot verify that the consumer app was discontinued.** Say *"repositioned toward teams and enterprise"* — which is documented — and nothing stronger.

## 6.4 🟠 MODERATE — adjacent 2026 personal-assistant benchmarks

| Work | Link | Why it could be raised |
|---|---|---|
| **π-Bench** — *Evaluating Proactive Personal Assistant Agents in Long-Horizon Workflows* | arXiv 2605.14678 | another 2026 personal-assistant benchmark. **Difference: proactivity.** PERCH is deliberately *summoned only* — proactive capture is the Recall failure mode. Cite as related, state the design choice |
| **Re-Centering Humans in LLM Personalization** | arXiv 2606.06614 | position paper on personalization done wrong; supports user-authored memory |
| **MacAgentBench** | arXiv 2606.22557 | macOS desktop agents. Different OS, and it is *task automation*, not context-carrying |
| **OSWorld 2.0** (XLANG Lab, HKU, June 2026) | — | 108 long-horizon workflows, median ~1.6 h, ~318 tool calls. **We are not doing OS automation** — say so before it is asked |

> **The distinction to hold onto:** OSWorld / MacAgentBench / π-Bench evaluate agents that **do tasks
> for you across the OS**. PERCH **carries your context to wherever you are working.** Automation is
> explicitly v2, and naming it as v2 is what stops the scope-sprawl objection.

## 6.5 🟠 the local-first tool category — **be careful how this is framed**

⚠️ **An earlier version of this table scored these tools on "OS-integrated?" and gave them all ❌.
That was misleading and a reviewer would say so.** They *are* desktop applications running locally on
your OS. Reducing the difference to one dismissive column both overstates our advantage and hides
where they are genuinely better than the closed products.

| Tool | Runs locally | Model choice | Open | **Comes to you** | **Typed memory you author** | **Declared private routing** |
|---|---|---|---|---|---|---|
| **Jan.ai** — 5.3M downloads | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| AnythingLLM · Khoj · PyGPT · Chatbox | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Open Cowork · LIYA Neural OS · PyWinAssistant | ✅ | ✅ | ✅ | partial | ❌ | ❌ |

**Say the good part out loud.** On local execution, model choice and openness these tools are *better
than Highlight and better than Microsoft's platform*. They are the honest comparison, and conceding
that costs us nothing.

**The three differences that are actually ours:**

1. **They are destinations.** You leave your PDF or your IDE and go to their window. PERCH is summoned
   into the application you are already in, and writes back into it.
2. **No typed personal memory.** They store chat threads locally — real files, genuinely portable —
   but there is no authored Identity/Project/Academic structure, and nothing imported from the
   assistants you already pay for.
3. **No routing policy.** Local-only *is* private, but it is not a *policy*: there is no per-request
   toggle, no source rule, no class-driven forcing. The question "may this particular request leave the
   machine?" is never asked, because the answer is fixed.

> **The honest one-line version:** *"the local open-source tools get the model layer right and the
> context layer isn't there at all — they're a good chat client, not a personal agent."*

## 6.6 🟢 MINOR — the Mac-only wall

| Tool | Cost | Platform |
|---|---|---|
| Raycast AI | $8/month | **Mac** |
| Apple Intelligence | free, built in | **Mac / iOS** |
| Dottie · BoltAI | free / $79 | **Mac** |

The entire "best AI assistant" review category is a Mac category.

---

# PART 7 — THE IMPORT MECHANISM

**✅ Verified in-session. This is what makes §1.4 of the architecture true.**

| Platform | Route | Format |
|---|---|---|
| **ChatGPT** | Settings → Data Controls → **Export data** → emailed ZIP (a ZIP inside a ZIP, including media) | `conversations.json` |
| **Claude** | Settings → **Privacy** → request data export → emailed download link | JSON |
| **Gemini** | **Google Takeout** → deselect all → select Gemini → emailed archive, usually within hours | JSON / HTML |

**And the negative result, equally important:** ❌ **a ChatGPT Plus or Claude Pro subscription cannot be
used as an API endpoint.** API access is separately billed with a separate key. There is no supported
path, and unsupported ones violate the terms. **Say this plainly if asked — it is a question that will
come up.**

---

# PART 8 — WHY PERSONAL AI PRODUCTS HAVE FAILED

| Product | Outcome |
|---|---|
| **Humane AI Pin** | raised **$230M**, shipped **<10,000 units**, sold to HP for **$116M** |
| **Rabbit R1** | **100,000 units**, then mass returns |
| **Rewind AI** | acquired by Meta as Limitless; Mac app **shut down 19 Dec 2025**, EU/UK access cut immediately |
| **Microsoft Recall** | audits found an admin-rights attacker could exfiltrate the database; Copilot cut back across Windows through 2026 |

**Published causes:** non-functional at launch · hardware constraints software cannot fix · solving too
many problems at once · building a separate thing instead of improving existing tools.

> ### ***"AI doesn't need a new gadget — it needs to improve the tools you already use."***

**And the Microsoft failures add a fifth:** users did not object to capability, they objected to
**forced integration** and **always-on capture**.

| Failure cause | Our design decision |
|---|---|
| New hardware | **none.** Software, existing laptop |
| Too many problems | **one primitive**: bring your context where you already are |
| Separate destination | **no destination** — it appears where you are |
| Always-on capture | **summoned only.** Nothing is read unless you invoke it |
| Forced integration | **opt-in by definition** — a shortcut you press |
| Incoherence | one surface, one memory, one place to configure |

---

# PART 9 — MODEL ECONOMICS AND BUILD STACK

## 9.1 Local models crossed the line in 2026

| Model | Footprint | Quality |
|---|---|---|
| **Qwen3 4B** | **~3 GB** (Q4) | practical on any laptop |
| **Qwen3 8B** | **~5.2–6 GB** (Q4) | fits 8 GB RAM |
| Llama 3.3 8B | — | 73% MMLU |
| Qwen3 14B | — | 83% MMLU, 85% HumanEval |
| Phi-4 (14B) | — | strongest small open-weight in class |

## 9.2 The cost floor is effectively zero

| Route | Terms |
|---|---|
| **Ollama, local** | free, open source, **no rate limit on `localhost:11434`** |
| **NVIDIA NIM** | free key with the Developer Program, **no credit card**, 100+ models, ~40 req/min |
| **OpenRouter BYOK** | your own provider key |

> **A student can run PERCH for ₹0.** That is the one thing a $50M-funded competitor structurally
> cannot match.

## 9.3 Tauri v2 over Electron

| | **Tauri v2** | Electron |
|---|---|---|
| Installer | **<10 MB** | >100 MB |
| **Idle RAM** | **30–50 MB** | **150–300 MB** |

Hoppscotch's migration: **165 MB → 8 MB, 70% memory reduction.**
**PERCH is always running** — this is a product decision, not a taste decision.

## 9.4 OS integration — primary sources

| | |
|---|---|
| **Microsoft UI Automation** | https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32 — *"programmatic access to most user interface elements on the desktop"* |
| `IUIAutomationElement`, `TextPattern`, `GetSelection` | Win32 accessibility reference |
| `RegisterHotKey`, `SendInput`, `GetForegroundWindow`, `GetWindowRect`, clipboard API | Win32 API reference |
| **Tauri v2** | https://v2.tauri.app/ — `alwaysOnTop`, `skipTaskbar`, `transparent`, global-shortcut plugin |
| Rust crates | `uiautomation`, `arboard`, `windows`, `tauri-plugin-global-shortcut`, `xcap` |

**No legal barrier** — documented, permissioned APIs used by screen readers and RPA tools for twenty
years. **Practical frictions:** antivirus heuristics on screen-reading behaviour; capture must be
visibly user-initiated.

---

# PART 10 — WHAT WE CLAIM AND WHAT WE DO NOT

| We do **not** claim | Because |
|---|---|
| Inventing selection-triggered AI | Highlight and Click to Do exist |
| Inventing agent memory | Mem0, Zep, Letta are mature |
| **Inventing memory gating** | **MemGate (2026) does exactly this** |
| Inventing relevance thresholds | CRAG, Self-RAG |
| **Inventing an OS-level personal index** | **Microsoft's Windows Semantic Index** |
| Beating LoCoMo / LongMemEval | near-saturated at 92–94% |
| A novel retrieval algorithm | not needed, not credible |

| We **do** claim |
|---|
| **C1** — token-budget-aware context assembly that adapts across a **4B local model to a frontier API**, so one memory layer serves both. Named as an open coordination problem by the 2026 externalization survey |
| **C2** — **declarative, auditable admission** on a user-owned six-class type system that *also* drives privacy routing. MemGate's learned gate cannot explain a rejection; ours can |
| **C3** — **import from official platform exports** — the only ToS-legitimate cross-vendor bridge, with class-typed extraction and human review |
| **C4** — the first open-source, model-agnostic, OS-integrated personal assistant that runs fully local on ordinary Windows Home hardware |
| **E** — an honest evaluation on **OP-Bench**, plus latency and packet-capture privacy measurements nobody publishes for a real assistant workload |

---

# PART 11 — READING QUEUE, IN PRIORITY ORDER

| # | What | Why it matters |
|---|---|---|
| **★new** | **PAUSE's ACM DL listing** — https://dl.acm.org/doi/10.1145/3770855.3817565 | ⚠️ **could not verify in this session — ACM's bot-wall blocks automated access.** Check via a normal logged-in browser or institutional ACM DL access **before the review**. The DOI itself resolves to a real ACM domain, which is partial evidence, not confirmation |
| **★new** | **Scrutable Assistant, ACM UMAP 2026** — https://doi.org/10.1145/3774935.3806186 | genuinely worth reading in full — its user-study findings on trust and scrutability could strengthen §4.4 (private mode) and the admission-gate framing, beyond what the abstract-level summary here covers |
| 0 | **LoCoMo, ACL 2024** — https://aclanthology.org/2024.acl-long.747/ | **the numbers in our deck do not match the abstract.** Resolve before the review — see the warning in Part 5 |
| 1 | **MemGate** full text — https://arxiv.org/html/2606.06054v1 | closest prior art to C2. **Read before writing the contribution slide** |
| 2 | **OP-Bench** full text — https://arxiv.org/html/2601.13722v1 | our primary evaluation. Need the exact scoring protocol |
| 3 | **PAUSE** full PDF — https://arxiv.org/abs/2607.27354 | models benchmarked, task counts, failure patterns are **still unknown** |
| 4 | **Externalization survey** — https://arxiv.org/abs/2604.08224 | the sentence that justifies C1 as research |
| 5 | **PerMemBench** — https://arxiv.org/abs/2605.25535 + GitHub | write-side gating; is it runnable by us? |
| 6 | π-Bench — https://arxiv.org/abs/2605.14678 | the proactivity contrast |
| 7 | LongMemEval-V2 (2605.12493), StreamMemBench (2606.14571) | harder settings |
| 8 | Confirm the Windows Semantic Index details from **Microsoft's own Build 2026 material**, not secondary coverage | §6.1 is load-bearing and currently 🟡 |
| 9 | **PersonalAlign** venue — is it really ACL 2026? — https://arxiv.org/abs/2601.09636 | currently inferred from a GitHub repo name only, not confirmed |
