"""
Build PERCH_Project_Review.pptx from the SENTINEL deck as a template.

The SENTINEL deck is a Google-Slides export of the college template, so all
branding (header bar, footer strip, logo, Times New Roman) lives in the slide
shapes themselves rather than in the master. So we do not rebuild the template:
we keep the title slide, clone the content slide and the flow-diagram slide as
prototypes, and rewrite every string inside them.

    pip install python-pptx
    python docs/build_deck.py

The template lives outside this repo (it belongs to the previous project), so
override its location with PERCH_DECK_TEMPLATE if things move.
"""

from __future__ import annotations

import copy
import math
import os
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = HERE.parent.parent / "docs" / "SENTINEL_Project_Review.pptx"
SRC = Path(os.environ.get("PERCH_DECK_TEMPLATE", DEFAULT_SRC))
OUT = HERE / "PERCH_Project_Review.pptx"

BODY = "Google Shape;103;p9"
TITLE = "Google Shape;94;p9"
PAGENUM = "Google Shape;102;p9"
BRAND = "Google Shape;85;p8"
DIAG_TITLE = "Google Shape;175;p14"
DIAG_PAGENUM = "Google Shape;184;p14"

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

# Body box geometry, used to check that nothing overflows.
BOX_W_IN = 4.65
BOX_H_IN = 3.30


# --------------------------------------------------------------------- helpers

def para_set(p, pieces, size=None):
    runs = p.findall(A + "r")
    if not runs:
        return
    proto = copy.deepcopy(runs[0])
    for r in runs:
        p.remove(r)
    for text, bold in pieces:
        r = copy.deepcopy(proto)
        rPr = r.find(A + "rPr")
        if rPr is not None:
            rPr.set("b", "1" if bold else "0")
            if size is not None:
                rPr.set("sz", str(int(size * 100)))
        r.find(A + "t").text = text
        p.append(r)


def shape_by_name(slide, name):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    return None


def set_plain(shape, text, size=None):
    para_set(shape.text_frame.paragraphs[0]._p, [(text, False)], size)


def set_body(slide, bullets, size=None):
    tf = shape_by_name(slide, BODY).text_frame
    proto = copy.deepcopy(tf.paragraphs[0]._p)
    txBody = tf._txBody
    for p in list(txBody.findall(A + "p")):
        txBody.remove(p)
    for lead, rest in bullets:
        p = copy.deepcopy(proto)
        pieces = []
        if lead:
            pieces.append((lead, True))
        if rest:
            pieces.append((rest, False))
        para_set(p, pieces or [(" ", False)], size)
        txBody.append(p)


def fix_pagenum(slide, total, name=PAGENUM, index=None):
    sh = shape_by_name(slide, name)
    if sh is None:
        return
    for p in sh.text_frame.paragraphs:
        for r in p.runs:
            if "/" in r.text:
                r.text = f" / {total}"
        if index is not None:
            for fld in p._p.findall(A + "fld"):
                t = fld.find(A + "t")
                if t is not None:
                    t.text = str(index)


def delete_slide(prs, index):
    lst = prs.slides._sldIdLst
    slides = list(lst)
    rId = slides[index].get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    prs.part.drop_rel(rId)
    lst.remove(slides[index])


def clone(prs, layout, proto_elements):
    new = prs.slides.add_slide(layout)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    tree = new.shapes._spTree
    for el in proto_elements:
        tree.append(copy.deepcopy(el))
    return new


# --------------------------------------------------------------------- content

SUB = "A Personal AI Agent That Lives Where Your Desktop Lives, Not Inside an Application"

SLIDES: list[dict] = []


def S(title, bullets, size=None, kind="text"):
    SLIDES.append({"kind": kind, "title": title, "bullets": bullets, "size": size})


S("Outline", [
    ("Introduction", " - Nobody Uses One AI Any More"),
    ("Problem Statement", " - Your Context Is Trapped Per-Vendor"),
    ("Evidence", " - A Measured Failure, and Two Expensive Precedents"),
    ("Scope, Objectives and Existing Work", ""),
    ("System Architecture", " - Four Layers, One Request Path"),
    ("Layer 1", " - The OS Surface, and What Already Runs"),
    ("Layer 3", " - Six Memory Classes, and Importing What Is Stranded"),
    ("Contribution 2", " - The Ranker and the Admission Scorer"),
    ("Contribution 1", " - Budget Assembly Across Heterogeneous Models"),
    ("Private Mode, Tools and Execution", ""),
    ("Technologies, Benchmarks and Evaluation Plan", ""),
    ("Base Paper, The Gap, Expected Results", ""),
    ("Conclusion and References", ""),
])

S("Introduction - Nobody Uses One AI Any More", [
    ("The situation:", " a typical user runs ChatGPT for general questions, Claude Code or Copilot "
     "for programming, Perplexity for research, and Gemini inside Docs."),
    ("The consequence:", " each one holds a separate, private memory of you. None of them can see "
     "the others. Your context is fragmented across the vendors you pay."),
    ("It is expensive:", " $70-110 a month across four subscriptions, and 15-30 minutes of context "
     "lost on every platform switch."),
    ("It is not settling down:", " ChatGPT's assistant market share fell from ~60% in early 2025 to "
     "under 45% by Q1 2026. People move constantly, and the context does not move with them."),
    ("What users now optimise for:", " the 2026 switching analysis found users prioritising "
     "governance and data portability over interface quality. Ownership is the deciding factor."),
])

S("Introduction - The Concrete Version", [
    ("A real workflow, not a hypothetical.", " Your college details, background and career context "
     "live in ChatGPT. Everything about your final-year project - the stack, the bugs, the design "
     "decisions, the timeline - lives in Claude Code, spread across dozens of sessions."),
    ("Neither can see the other.", " So when you need a 200-word project summary for an application "
     "form, neither one can write it. ChatGPT does not know the project. Claude Code does not know "
     "the form, and its knowledge is scattered across sessions it will not surface."),
    ("You do the merge manually, in your head, every single time.", ""),
    ("The knowledge already existed.", " It was locked inside a session, in a product that will "
     "never share it. That is what PERCH exists to remove."),
])

S("Problem Statement", [
    ("In one sentence:", " every assistant's memory of you is owned by the vendor of that assistant, "
     "so personal context cannot follow you across the tools you actually use."),
    ("This is measured, not asserted.", " PAUSE (ACM SIGKDD 2026) found state-of-the-art proprietary "
     "models fail to reach 70% task completion on scenarios requiring stateful reasoning and "
     "configuration awareness."),
    ("Read that carefully:", " the failure is not the model's reasoning. It is the state around the "
     "model - persistent knowledge of who the user is and what they are working on."),
    ("The second half is location.", " Every assistant is a destination. You leave your document, "
     "your IDE or your PDF, go to a window, paste, read, and carry the answer back."),
    ("So the problem is two-part:", " personal context is trapped per-vendor, and the assistant that "
     "would use it is trapped inside an application."),
], size=10.5)

S("Proof This Is Real - Measured, Not Asserted", [
    ("ACM measurement.", " PAUSE, KDD 2026: frontier models below 70% task completion when the task "
     "requires reasoning over persistent user state."),
    ("An established research category.", " The Tsinghua AIR survey defines agents deeply integrated "
     "with personal data and devices, naming context sensing and memorization as fundamental unsolved "
     "capabilities. We flag it ourselves as a preprint - it carries vocabulary here, not authority."),
    ("An IEEE forecast, for scale.", " The IEEE Global Study of 400 technology leaders puts personal "
     "assistant and calendar management as the top expected mass-adoption use of agentic AI in 2026, "
     "at 52%."),
    ("And a warning we take seriously.", " OP-Bench (2026) measures over-personalisation and finds "
     "memory-augmented assistants score 26.2% to 61.1% WORSE than memory-free baselines. Naive "
     "memory injection makes an assistant worse than having no memory at all."),
    ("Market behaviour.", " $70-110/month across four assistants; 15-30 minutes lost per switch; "
     "market share moving 15 points in a year."),
    ("Capability that did not exist in 2024.", " Qwen3 4B runs in ~3 GB and Qwen3 8B in ~5-6 GB "
     "quantised, so a genuinely useful local model now fits on an ordinary student laptop."),
], size=9.5)

S("Can We Use the Subscriptions You Already Pay For?", [
    ("The ideal design is impossible.", " There is no cross-vendor memory API and there will not be "
     "one. Memory is the switching cost, so a vendor exposing it would be funding its own churn. "
     "There is no standard, and no company exports health or employment content to a third party."),
    ("Routing our model calls through your ChatGPT Plus or Claude Pro subscription: NO.",
     " Subscriptions cover the vendor's own client. API access is separately billed with a separate "
     "key. There is no supported path, and unsupported ones violate the terms."),
    ("Pulling your conversation history out of them: YES, officially, on every major platform.", ""),
    ("ChatGPT", " - Settings, Data Controls, Export data. Emails a ZIP containing conversations.json."),
    ("Claude", " - Settings, Privacy, request data export. Emails a JSON archive."),
    ("Gemini", " - Google Takeout, select Gemini only. Emails JSON within hours."),
    ("That export button is the bridge.", " It is a feature of the subscription you already pay for, "
     "it is required by regulators, and it is the only ToS-legitimate way to move a vendor's memory "
     "of you into something you own. PERCH parses those archives locally."),
], size=9.5)

S("Why This Position Is Open - and the Microsoft Objection", [
    ("A neutral context layer is against every model vendor's business model.", " OpenAI wants you "
     "in ChatGPT, Google in Gemini, Microsoft in Copilot, Apple on a Mac."),
    ("The real objection, stated first and honestly.", " At Build 2026 Microsoft announced the "
     "Windows AI Platform: a Copilot Runtime, an AI Orchestrator, and a Windows Semantic Index - a "
     "personal semantic index enabling persistent agent memory and context. That is our Layer 3, "
     "being built into the operating system."),
    ("Four verifiable answers.", " It is unshipped - Copilot Runtime targets Windows 11 26H2. It is "
     "edition-gated - initial rollout targets 24H2 Enterprise and Pro with VBS and SLAT, not Home. "
     "It documents no third-party access, so you cannot point your own model at it. And Microsoft "
     "killed Copilot features and merged the Copilot apps in August 2026."),
    ("So: Microsoft validates the architecture and closes it.", " We run on Home edition, today, on "
     "any model including one that never leaves the machine."),
    ("The other near-competitor left.", " Highlight AI raised $40M Series A in March 2026 and "
     "repositioned as a shared intelligence layer for teams and enterprise."),
], size=10)

S("What the Expensive Failures Taught Us", [
    ("Humane AI Pin:", " raised $230M, shipped fewer than 10,000 units, sold to HP for $116M."),
    ("Rabbit R1:", " sold 100,000 units, then took mass returns."),
    ("Rewind AI:", " acquired by Meta as Limitless; the Mac app shut down 19 December 2025."),
    ("Microsoft Recall:", " audits found an admin-rights attacker could exfiltrate the database."),
    ("The published lesson, verbatim:", " \"AI doesn't need a new gadget - it needs to improve the "
     "tools you already use.\""),
    ("Every stated cause maps to a design decision.", " No hardware. One primitive, not four. No "
     "destination - it appears where you are. Summoned only, never always-on capture. Opt-in by "
     "definition, because it is a shortcut you press."),
])

S("Scope & Objectives", [
    ("Scope:", " a desktop-resident personal AI agent for Windows. Dormant in the background, "
     "summoned by a selection, screenshot or shortcut in any application, answering in a slim panel "
     "beside your work and writing back into the document you were in."),
    ("O1 - Surface.", " Three triggers, panel placement beside the host window without stealing "
     "focus, and edit-in-place with no per-application plugin."),
    ("O2 - Context assembly.", " Decide what enters the prompt under a hard ceiling set by whichever "
     "model is selected, from a 4B local model to a frontier API."),
    ("O3 - Memory.", " Six typed classes, user-authored and importable, stored as files the user can "
     "open, edit, export or delete - with an admission gate that refuses to inject weak matches."),
    ("O4 - Execution.", " Model-agnostic routing, a full agent tool surface, and a private mode that "
     "provably sends nothing."),
    ("Out of scope, and named as such:", " adaptive automatic model routing, multi-device sync, "
     "shell execution and app automation are all v2."),
], size=10)

S("Existing Work - Our Real Competition", [
    ("Highlight AI", " - $50M, 500,000+ users, Mac and Windows, selection-triggered and screen-aware. "
     "Cloud-dependent, rate-limited, no model choice, closed source, repositioned to teams in "
     "March 2026."),
    ("Microsoft Windows AI Platform", " - the same architecture from the OS vendor, but unshipped, "
     "Enterprise/Pro-gated, closed to third parties, and locked to their models."),
    ("Raycast AI, Apple Intelligence, Dottie, BoltAI", " - the entire \"best AI assistant\" review "
     "category is a Mac category. None of these run on Windows."),
    ("Jan.ai (5.3M downloads), AnythingLLM, Khoj, PyGPT, Chatbox", " - right philosophy, wrong shape. "
     "All local-capable and open, and every one is an application window you open."),
    ("The pattern:", " tools that are OS-integrated are closed, cloud-only or hardware-gated. Tools "
     "that are local and open are destinations you have to visit."),
], size=10.5)

S("The Positioning Table - The Empty Row", [], kind="table_position")
S("Layer 1 - Three Triggers, Two Capture Paths", [
    ("T1 - Global hotkey.", " Win32 RegisterHotKey gives a system-wide shortcut that fires regardless "
     "of which application has focus. Rust: tauri-plugin-global-shortcut, a first-party Tauri v2 plugin."),
    ("T2 - Read the current selection. The hard one, so it has two paths.", ""),
    ("Path A - UI Automation.", " GetFocusedElement, TextPattern, GetSelection, GetText. This is the "
     "documented Windows accessibility framework that exists so screen readers can do exactly this. "
     "A supported path, not a hack."),
    ("Path B - clipboard round-trip.", " Save the clipboard, write a unique sentinel, send Ctrl+C, "
     "poll until it changes, restore the original. Less elegant, works essentially everywhere."),
    ("Design rule:", " try A, fall back to B, and log which one worked per application. That per-app "
     "coverage table is a deliverable - no competitor publishes one."),
    ("T3 - Screenshot.", " Transparent full-screen overlay, drag a region, capture, optional OCR."),
], size=10)

S("Layer 1 - Edit In Place, and Why There Is No Plugin", [
    ("This is what separates PERCH from a chat window.", " A chat window can only hand you text to "
     "copy. PERCH writes the answer back into the application you came from."),
    ("The mechanism:", " put the answer on the clipboard, restore focus to the original window using "
     "the HWND saved at trigger time, send Ctrl+V, then restore the user's previous clipboard."),
    ("Why replacement needs no app-specific integration:", " in every text field on Windows, pasting "
     "while text is selected replaces that text. We use behaviour every text field already has."),
    ("Three actions:", " Replace overwrites the selection, Insert after appends below it, Copy only "
     "changes nothing. If Windows refuses the focus change we do not paste - landing in the wrong "
     "window is worse than not pasting."),
    ("Rejected alternative - per-application plugins.", " An Office add-in, a VS Code extension and a "
     "browser extension mean N integrations, N review processes, and it only works where we shipped."),
], size=10.5)

S("What Already Runs - The Prototype", [
    ("We built the risky layer first, then the pipeline on top of it.", " The application and agent "
     "layers are familiar work; whether a desktop app can genuinely reach into other applications "
     "was not. It can, and it is running."),
    ("OS layer, verified:", " system-wide hotkey; selection read from other applications via UI "
     "Automation with clipboard fallback; region screenshot; panel docked beside the host; focus "
     "restore and paste-back."),
    ("Agent layer, running:", " six typed memory classes stored as Markdown with a SQLite index; "
     "intent and class routing; ranker; admission scorer; budget packer; model registry with local "
     "and cloud routes; and a tool surface covering web, files, documents, OCR and Python. The tool "
     "loop runs on the local model too, so the full agent works at zero cost."),
    ("What the demo shows while it runs:", " answers stream token by token, and a live tracker lights "
     "up each pipeline stage in turn - route, rank, gate, pack, model - with the gate reporting what "
     "it admitted and dropped. It turns GREEN when it admits and RED when it abstains, because a "
     "deliberate refusal is the contribution working, not a failure."),
    ("Verification:", " 25 tests pass with no model, no GPU and no network. The ablation runs on a "
     "seeded memory set and prints every routing, ranking and admission decision."),
], size=9.5)

S("Layer 3 - Six Memory Classes, Open Tags", [
    ("The design rule: few classes, many tags.", " A class is a routing decision, and every class we "
     "add is another chance for the router to be wrong. Fine distinctions go in tags, which only "
     "refine ranking inside an already-chosen class and cannot cause a routing miss."),
    ("Identity", " - who you are, how you want answers written, standing instructions. Small, cheap, "
     "and relevant to almost everything."),
    ("Project", " - purpose, stack, architecture decisions and why, problems and how each was fixed, "
     "timeline, results, open items."),
    ("Academic", " - institution, semester, subjects, assessment format, conventions, deadlines."),
    ("Career", " - roles, skills, applications, interviews, targets."),
    ("Health and Personal", " - conditions, medications, allergies; relationships, preferences, "
     "commitments. Both are private by default, so the type system doubles as the privacy primitive."),
    ("Storage:", " one Markdown file per item with YAML frontmatter. The files are the truth; the "
     "SQLite vector index is derived and rebuildable. Memory you cannot read is memory you cannot trust."),
], size=9.5)

S("Layer 3 - Importing What Is Stranded in Your Other AIs", [
    ("Three import paths, in order of value.", ""),
    ("1. Platform export - the primary one.", " Drop the emailed archive in. PERCH parses it locally, "
     "segments sessions, runs class-typed extraction, and presents proposed items for review. Nothing "
     "is stored until you accept it."),
    ("2. Live", " - you tell PERCH something and mark it worth keeping."),
    ("3. Extraction prompt", " - for one specific session, or a platform with no export. Paste the "
     "class prompt in, paste the structured block back."),
    ("One contract, six schemas.", " The output format is fixed and identical for every class so the "
     "importer can parse it; the schema - what the body must cover - is chosen by the user before "
     "extraction. One vague prompt returns prose that cannot be typed or gated; six unrelated prompts "
     "produce six incompatible formats."),
    ("The user picking the class is what makes the item typed at the source", ", and typing at the "
     "source is what makes the admission gate auditable instead of learned."),
    ("Scale is bounded by design:", " near-duplicates merge above cosine 0.92 rather than "
     "accumulating, each class has an item ceiling, and nothing is stored silently."),
], size=9.5)

S("Where It Pays Off - One Example Per Class", [
    ("Identity", " - every assistant must be told, every session, how you write. Stored once, applied "
     "in every application, including offline."),
    ("Academic", " - select a dense paragraph in a course PDF and ask how it connects to the "
     "optimisation unit. PERCH knows your syllabus, semester and department. ChatGPT does not, and "
     "you would describe it again next week."),
    ("Project", " - select a stack trace in your IDE. PERCH knows the stack, the architecture "
     "decision that caused it, and that you fixed the same async-context problem in March."),
    ("Career", " - a recruiter emails. Trigger in the reply window: Career supplies target roles, "
     "Project supplies what you actually built, Identity supplies the tone."),
    ("Health", " - a prescription changes and you want to prepare questions. This is answered by the "
     "local model with zero bytes leaving the machine. It is not a better-answer argument, it is the "
     "only version of this that is acceptable to run at all."),
    ("The cross-class case no other AI can do:", " a statement of purpose needs Identity, Academic, "
     "Project and Career at once. No other assistant has all four, because no other assistant is "
     "allowed to."),
], size=9.5)

S("The Failure Every Memory System Ships", [
    ("The scenario.", " You ask a question about your medication. Your memory holds no health items "
     "at all - the only place the word medical appears is an academic note saying your engineering "
     "campus shares a road with the group's medical college."),
    ("What a naive system does.", " Semantic search returns the college item, the ranker makes it "
     "rank one because it is the best of what exists, and the assistant answers a medical question "
     "with your college details."),
    ("This is named and measured in the 2026 literature.", " MemGate calls it cross-domain leakage - "
     "a memory unit that satisfies the semantic ranking criteria but violates contextual "
     "admissibility - and reports it at 27.0% before mitigation."),
    ("OP-Bench measures the damage.", " Systems retrieve at ~80% similarity even in deliberately "
     "baited cases, attend to memory tokens twice as much as to the user's own query, and score "
     "26.2% to 61.1% worse than memory-free baselines."),
    ("The consequence for this project:", " retrieval that does not know when to stay quiet is a "
     "liability, not a feature. An admission gate is not a refinement - it is what makes memory a "
     "net positive at all."),
], size=10)

S("Contribution 2 - The Ranker and the Admission Scorer", [
    ("Ranking is relative. Injection must be absolute.", ""),
    ("The ranker", " orders candidates by similarity to the question and selection, tag overlap, "
     "entity match, recency and use, and a per-class prior. Its output is an ORDER - and an order "
     "says nothing about whether the best item is any good."),
    ("The admission scorer", " then applies two different tests. An absolute floor per class: if a "
     "class's best candidate scores below its floor, that class contributes NOTHING, rather than the "
     "best of a bad lot. And a margin test inside an admitted class, because an item far below that "
     "class's best is filler, and filler is what burns budget."),
    ("If no class is admitted, PERCH abstains", " - it answers from general knowledge and says it has "
     "nothing stored. LongMemEval scores abstention as an ability, so this is measurable."),
    ("Prior art, cited by us first.", " MemGate does this with a learned neural gate; CRAG with a "
     "retrieval evaluator and threshold; Self-RAG with trained reflection tokens. We did not invent "
     "gating."),
    ("What is ours:", " the gate is declarative, not learned. The class is assigned at import time, "
     "the floor is per class, and every drop carries a reason. A learned gate cannot tell you why it "
     "dropped your memory; a personal agent has to be able to."),
], size=9.0)

S("The Ablation - What We Measured", [], kind="table_ablation")

S("Contribution 1 - Budget Assembly Across Models", [
    ("The formula:", " budget = context_window(model) minus reserves for the response, the system "
     "prompt and the tool schemas."),
    ("Fill order is a strict priority", " - system and identity always; the selection always, because "
     "it is why the user summoned us; recent conversation with oldest truncated first; then admitted "
     "memory into whatever remains; then tool results claimed from the same allowance."),
    ("Items enter whole or not at all.", " Half a project decision is worse than none - it reads as a "
     "confident, incomplete fact."),
    ("This is what makes model choice real.", " Swap a local Qwen3 4B for a frontier API and the "
     "budget recomputes. Nothing else changes. One memory layer serves a 3 GB local model and a "
     "200,000-token frontier model."),
    ("Why this is research and not engineering.", " The 2026 externalization survey states that the "
     "context window remains the scarcest shared resource, with memory, skills, tool schemas and "
     "reasoning traces all competing for one finite budget - and calls it a harness-level "
     "coordination problem. It names the problem and leaves it open for this span."),
], size=10)

S("Private Mode - Declared, Never Inferred", [
    ("Classification is the wrong answer here.", " Deciding what is private from the content itself "
     "means a classifier whose false-negative cost is leaking a company secret to a cloud API. No "
     "accuracy figure makes that acceptable."),
    ("1. Per-request toggle.", " A Private switch on the panel, visible before you send."),
    ("2. Source rules - the useful one.", " Declare a source private once: this application, this "
     "folder, or this window-title pattern. PERCH knows the source at capture time, so it never needs "
     "to understand the text, only where it came from. Deterministic, auditable, no model involved."),
    ("3. Global default.", " Local by default, escalate to cloud explicitly."),
    ("4. Class-driven, free from the type system.", " Health and Personal are private classes, so any "
     "request that admits one is forced local automatically, with the panel saying why."),
    ("And private mode does not merely refuse the network tools - it never declares them.", " A "
     "privacy guarantee that leaks through a search query is not a guarantee."),
    ("The demonstrable claim:", " zero bytes leave the machine, provable with a packet capture."),
], size=9.5)

S("Layer 4 - Execution, Tools and the Cost Floor", [
    ("Model registry.", " Each entry holds provider, endpoint, model id, context window, tool support "
     "and whether it is local. Everything upstream reads context_window from here."),
    ("The full agent tool surface:", " web search and fetch; memory search, write, update and forget; "
     "file read, write, list and search within declared roots; PDF, DOCX and PPTX parsing; OCR; "
     "region capture, selection read, clipboard and paste-back; open path, URL and window; and "
     "sandboxed Python for arithmetic and data work."),
    ("Tool policy:", " read is free, write asks and shows what it will do, every call is logged in "
     "the panel, and private mode removes the network tools entirely."),
    ("Routes.", " Ollama on localhost - free, no rate limit, Qwen3 4B in about 3 GB. NVIDIA NIM - "
     "free key, no credit card, 100+ models. Or your own key."),
    ("A student can run PERCH for zero rupees.", " That is the one thing a $50M-funded competitor "
     "structurally cannot match. Automatic adaptive routing is explicitly v2."),
], size=10)

S("Technologies Used", [
    ("Shell - Tauri v2.", " 30-50 MB idle against Electron's 150-300 MB, sub-10 MB installer against "
     "100 MB+. PERCH is always running, so a background assistant idling at 250 MB is one users "
     "uninstall. Hoppscotch's migration went 165 MB to 8 MB with a 70% memory reduction."),
    ("Core - Rust.", " Hotkeys, UI Automation, clipboard, window management, tray. Verified bindings: "
     "tauri-plugin-global-shortcut, the uiautomation crate, arboard, the official windows crate."),
    ("Interface - React and TypeScript.", ""),
    ("AI/ML - Python sidecar.", " Embeddings, ranker, admission scorer and packer, in the language "
     "the team already knows."),
    ("Storage - SQLite and Markdown files", ", with sqlite-vec for the vector index. No server."),
    ("Local inference - Ollama.", " Free, no rate limit."),
], size=10.5)

S("Datasets and Benchmarks", [
    ("OP-Bench - our primary target.", " 1,700 verified instances across 20 users, in three "
     "categories: irrelevance, repetition and sycophancy. It measures precisely the failure our "
     "admission gate prevents, and its baselines are bad on purpose."),
    ("LongMemEval", " - 500 questions across 6 categories, testing extraction, multi-session "
     "reasoning, temporal reasoning, knowledge updates and abstention. The abstention category "
     "validates the gate directly."),
    ("LoCoMo", " - 1,540 questions across 4 categories, ~300 turns, up to 35 sessions. Used for "
     "comparability with Mem0 and MemGate."),
    ("PerMemBench", " - multi-year multi-domain personalized memory, for the write-side gating policy."),
    ("Honest framing, stated up front:", " 2026 reference scores are LoCoMo 92.5% and LongMemEval "
     "94.4%. These are near-saturated and we do not pitch beating them. OP-Bench is where a number "
     "can genuinely move, because memory systems there score 26-61% worse than no memory at all."),
], size=10)

S("Evaluation Plan", [
    ("E1 - Over-personalisation, the headline.", " OP-Bench, against three baselines: no memory, "
     "naive top-k, and ours. We must beat both."),
    ("E2 - Budget assembly ablation (C1).", " No memory, full profile always injected, and "
     "budget-aware selection, measured at three model sizes. The margin should be largest on the "
     "smallest model, because that is where the budget actually binds."),
    ("E3 - Retrieval quality.", " LongMemEval and LoCoMo, reported honestly against published 2026 "
     "baselines."),
    ("E4 - Admission gate ablation (C2).", " Cross-domain leakage with the gate off, with a single "
     "global threshold, and with per-class floors. MemGate's 27.0% to 3.5% is the reference point."),
    ("E5 - Privacy.", " Bytes leaving the machine in private mode must be zero, by packet capture."),
    ("E6 - Latency.", " Trigger to first token, local versus cloud."),
    ("E7 - UI Automation coverage per application.", " A measured table across common Windows apps. "
     "No competitor publishes one."),
], size=10)

S("Base Paper - PAUSE, ACM SIGKDD 2026", [
    ("PAUSE: A User-Centric Benchmark for Personal AI Assistants in Unified Service Environments.",
     " ACM SIGKDD 2026, 9-13 August 2026, Jeju Island. Chen, Shi, Wang, Chen and Niu."),
    ("Why this is the base paper:", " ACM and 2026, and its subject is literally personal AI "
     "assistants - so it cannot be misread as a memory-architecture project."),
    ("Its definition is our specification.", " An assistant must reason over persistent user state, "
     "respect user-specific configurations and permissions, and sustain long-horizon, "
     "constraint-aware interactions across multiple services."),
    ("It hands us the gap, quantified:", " state-of-the-art proprietary models fail to reach 70% task "
     "completion on scenarios requiring stateful reasoning and configuration awareness."),
    ("Where it stops.", " PAUSE is a benchmark, evaluating assistants inside unified service "
     "environments that already have access and configuration. It does not build a system, does not "
     "address how a user supplies their own state, does not address OS-level capture, and does not "
     "address operating within a fixed token budget across heterogeneous models."),
], size=10)

S("Personal AI Is a Recognised Category, Not a Framing We Chose", [
    ("The concern this slide answers:", " if we do not explicitly separate ourselves, a reviewer maps "
     "any memory-carrying agent onto the nearest known project and stops looking further."),
    ("SIGKDD 2026 itself runs a dedicated workshop on this.", " PILA 2026 - Personal Intelligence in "
     "the Agentic AI Era, co-located with SIGKDD, 10 August 2026. Its scope: personalized agents, user "
     "modeling, memory and retrieval, adaptive planning, privacy and deployment. The top venue in this "
     "space has already drawn this exact line."),
    ("And it is not just a workshop.", " A Scrutable Assistant for Time Management is a full peer- "
     "reviewed paper at ACM UMAP 2026 - a 34-year-old conference series dedicated to user modeling and "
     "personalization. It studies a personal assistant users can scrutinise, down to the model behind "
     "its suggestions - independently arrived at, published, and close enough to our own admission "
     "gate that the field already has a name for it: scrutability."),
    ("So the line is not ours to defend alone.", " Personal AI assistants are a distinct, actively "
     "reviewed category at ACM's own venues in 2026, separate from memory-architecture research. We are "
     "answering a question the field already treats as its own."),
], size=10)

S("The Gap - What We Claim and What We Do Not", [
    ("We do NOT claim inventing selection-triggered AI", " - Highlight and Click to Do exist."),
    ("We do NOT claim inventing agent memory", " - Mem0, Zep and Letta are mature."),
    ("We do NOT claim inventing memory gating", " - MemGate does exactly this, with a learned gate."),
    ("We do NOT claim inventing an OS-level personal index", " - Microsoft's Windows Semantic Index."),
    ("C1 - budget-aware assembly across heterogeneous models.", " One memory layer serving a 4B local "
     "model and a frontier API, with an ablation at three model sizes. Named as an open coordination "
     "problem by the 2026 externalization survey."),
    ("C2 - declarative, auditable admission on a user-owned type system", " that also drives privacy "
     "routing. One primitive doing two jobs."),
    ("C3 - import from official platform exports", " - the only ToS-legitimate cross-vendor bridge."),
    ("C4 - the first open-source, model-agnostic, OS-integrated personal assistant", " that runs "
     "fully local on ordinary Windows Home hardware."),
], size=9.5)

S("Expected Results and Honest Limitations", [
    ("What we expect to show.", " Budget-aware assembly beating both naive conditions at every model "
     "size, with the largest margin on the smallest model. Zero leakage on OP-Bench irrelevance "
     "without losing identity context. Sub-second trigger-to-first-token locally. Zero bytes in "
     "private mode."),
    ("Known limitation - the per-class floors are tuned, not fitted.", " Cosine means different things "
     "to different embedders - we measured unrelated text at 0.35-0.41 on a real model but near 0.10 "
     "on the fallback. Scores are rescaled against a measured per-backend baseline; the honest next "
     "step is fitting floors on held-out labelled data."),
    ("Known limitation - six classes is a design choice, not a derivation.", " The defence is that "
     "classes are a routing device and each one is a new failure mode, so the burden is on adding a "
     "seventh. And it is testable: E1 measures whether routing helps or hurts."),
    ("Known limitation - import depends on export formats we do not control.", " They are "
     "undocumented JSON that can change without notice. Parsers are isolated per platform and fail "
     "loudly, the extraction-prompt path works with no export at all, and the review screen means a "
     "broken parser produces nothing rather than garbage."),
    ("Known limitation - UI Automation coverage varies by application.", " Hence the clipboard "
     "fallback, and why the coverage table is a documented deliverable."),
    ("Practical risk:", " screen-reading behaviour can trip antivirus heuristics, so the installer "
     "must be signed and capture must stay user-initiated."),
], size=9.0)

S("Conclusion", [
    ("The problem is not which AI you use.", " It is that your context is trapped inside whichever one "
     "you typed it into, and the assistant that would use it is trapped inside an application window."),
    ("The measurement backs it.", " ACM SIGKDD 2026 found frontier models below 70% when a task needs "
     "persistent knowledge of the user. OP-Bench found that adding memory naively makes things worse."),
    ("PERCH is the layer above the applications.", " Summoned anywhere in Windows, answering beside "
     "your work, writing back into the document you were in, remembering what you told it once, and "
     "running on whichever model you choose - including one that never leaves your machine."),
    ("The risky part is already built.", " The OS layer runs. So does the pipeline: routing, ranking, "
     "admission, packing, tools, and 25 passing tests."),
    ("The technical core is the retrieval gate and the budget packer", " - a calibration problem and "
     "a constrained-allocation problem, evaluated with four ablations on public benchmarks."),
    ("You pay for four AI assistants. None of them know you, and none of them will tell each other. "
     "PERCH is the one that's yours.", ""),
], size=10)

S("References - Peer-Reviewed Spine", [
    ("[1] PAUSE: A User-Centric Benchmark for Personal AI Assistants in Unified Service Environments.",
     " Chen, Shi, Wang, Chen, Niu. ACM SIGKDD 2026, Jeju Island. - BASE PAPER"),
    ("[1b] \"...Exploring User Perspectives on a Scrutable Assistant for Time Management.\"",
     " Landerberg, Flatmo, Said. ACM UMAP 2026, Full Paper. - second personal-AI anchor, non-benchmark"),
    ("[2] A Survey on the Memory Mechanism of LLM-based Agents.",
     " ACM Transactions on Information Systems 43(6), 2025. DOI 10.1145/3748302"),
    ("[3] Evaluating Very Long-Term Conversational Memory of LLM Agents (LoCoMo).",
     " ACL 2024, Long Papers. - evaluation benchmark"),
    ("[4] LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory.",
     " ICLR 2025. - evaluation benchmark, includes abstention"),
    ("[5] Self-RAG: Learning to Retrieve, Generate and Critique through Self-Reflection.",
     " Asai, Wu, Wang, Sil, Hajishirzi. ICLR 2024. - prior art for retrieve-or-not"),
    ("[6] Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory.",
     " ECAI 2025."),
    ("[7] From Storage to Experience: The Evolution of LLM Agent Memory Mechanisms.",
     " Findings of ACL 2026."),
    ("[8] Bridging Intuitive Associations and Deliberate Recall.", " Findings of ACL 2025."),
    ("[9] Memory in the LLM Era: Modular Architectures and Strategies.", " VLDB 2026."),
    ("[10] Microsoft.", " UI Automation Overview and Win32 Accessibility documentation; Tauri v2 "
     "documentation; Windows AI Platform, Build 2026."),
], size=8.5)

S("References - Current Preprints (2026)", [
    ("Cited as current state of the art, not as settled results.", " Each is two to seven months old, "
     "so nothing at that age has cleared peer review in any venue. None of them carries a claim on "
     "its own, and none is load-bearing for the base paper or the evaluation plan."),
    ("[11] Beyond Similarity: Trustworthy Memory Search for Personal AI Agents (MemGate).",
     " arXiv:2606.06054, June 2026. - closest prior art to Contribution 2"),
    ("[12] OP-Bench: Benchmarking Over-Personalization for Memory-Augmented Personalized "
     "Conversational Agents.", " arXiv:2601.13722, January 2026. - our primary evaluation target"),
    ("[13] Personalize-then-Store: Benchmarking and Learning Personalized Memory for Long-horizon "
     "Agents.", " KAIST. arXiv:2605.25535, May 2026. - write-side gating"),
    ("[14] Externalization in LLM Agents: A Unified Review of Memory, Skills, Protocols and Harness "
     "Engineering.", " arXiv:2604.08224, April 2026. - names our Contribution 1 as an open problem"),
    ("Two we flag ourselves, because age does not explain them.", " Personal LLM Agents (Tsinghua "
     "AIR, arXiv:2401.05459) has been a preprint since January 2024 with no venue - we use its "
     "vocabulary only, never as an authority. And CRAG (arXiv:2401.15884) was submitted to ICLR 2025 "
     "and withdrawn, so it is cited as an approach, not as a published result."),
], size=9.0)


# ------------------------------------------------------------- diagram content

ARCH_TITLE = "System Architecture - Four Layers, One Request Path"
ARCH_BOXES = [
    "USER   working in any Windows application - PDF, IDE, browser, email, form",
    "TRIGGER   L1   hotkey, selection or screenshot - nothing is read until you press it",
    "CAPTURE   L1   UI Automation, clipboard fallback; the host window handle is saved",
    "PRIVACY   L2   source rules, toggle, global default - decided before any model sees it",
    "ROUTE   L2   intent, then which of the six memory classes are eligible",
    "RANK + ADMIT   L3   per-class floor and margin - or admit nothing and abstain",
    "PACK   L2   budget = context_window(model) - response - system - tool schemas",
    "EXECUTE   L4   local Ollama, free tier or your own key + the agent tool loop",
    "EDIT IN PLACE   L1   answer beside your work, then back into the app you came from",
]
ARCH_NOTE = [
    "L2 and L3 are the contribution.",
    "",
    "L1 is already built and running.",
    "",
    "L4 is what makes it free.",
]

# ---------------------------------------------------------------------- tables

POSITION_ROWS = [
    ["", "Windows", "No special\nhardware", "Local\noption", "Cloud\nchoice",
     "Selection\ntriggered", "Individual\nuser", "Open\nsource"],
    ["Highlight AI", "Y", "Y", "N", "N", "Y", "N  teams", "N"],
    ["Windows AI Platform", "Y", "Y", "Y", "N", "Y", "N  Pro", "N"],
    ["Raycast / Apple", "N", "-", "partial", "partial", "Y", "Y", "N"],
    ["Jan.ai / PyGPT / Khoj", "Y", "Y", "Y", "Y", "N", "Y", "Y"],
    ["PERCH", "Y", "Y", "Y", "Y", "Y", "Y", "Y"],
]

POSITION_CAPTION = [
    ("Read the columns, not the rows.", " Every competitor fails at least one column that matters to "
     "an individual user on an ordinary Windows laptop."),
    ("Highlight is closed and cloud-only and has moved to teams. Microsoft's platform is unshipped, "
     "Enterprise/Pro-gated and closed to third parties.", " The Mac tools do not run here, and the "
     "local open tools are all windows you have to go to."),
    ("The bottom row is the project.", " Nothing in it is individually novel - the combination is the "
     "one nobody is shipping."),
]

ABLATION_ROWS = [
    ["Configuration", "Leaked items", "Useful context kept"],
    ["A   naive global top-k, no gate", "8", "3 / 3"],
    ["B   one global threshold", "0", "2 / 3"],
    ["C   ours: class routing + per-class floors", "0", "3 / 3"],
]

ABLATION_CAPTION = [
    ("Run it yourself: python -m app ablate.", " Five queries against a seeded memory that contains no "
     "health items at all - the only mention of \"medical\" is an academic note about the campus."),
    ("A is what most memory systems do.", " It answers a question about your medication with your "
     "college details - eight irrelevant items injected."),
    ("B is the interesting one.", " One global threshold stops the leak, but a threshold high enough "
     "to keep health memory out is also high enough to throw identity away, so \"rewrite this more "
     "formally\" stops sounding like you."),
    ("C keeps both.", " Per-class floors are the reason - and every drop prints its own reason, which "
     "a learned gate cannot do."),
]


# ----------------------------------------------------------------------- build

def add_table_slide(prs, slide, title, rows, caption, col0_w, table_top,
                    caption_top, total, colour_cells=True):
    set_plain(shape_by_name(slide, TITLE), title)
    set_plain(shape_by_name(slide, BRAND), "PERCH")
    fix_pagenum(slide, total)

    body = shape_by_name(slide, BODY)
    body._element.getparent().remove(body._element)

    ncols = len(rows[0])
    width = Inches(4.80)
    gf = slide.shapes.add_table(len(rows), ncols, Inches(0.12), Inches(table_top),
                                width, Inches(0.26 * len(rows)))
    table = gf.table
    table.columns[0].width = Inches(col0_w)
    rest = (4.80 - col0_w) / (ncols - 1)
    for c in range(1, ncols):
        table.columns[c].width = Inches(rest)

    tbl = table._tbl
    tbl.tblPr.set("firstRow", "1")
    tbl.tblPr.set("bandRow", "0")
    for el in tbl.tblPr.findall(A + "tableStyleId"):
        tbl.tblPr.remove(el)
    style = tbl.tblPr.makeelement(A + "tableStyleId", {})
    style.text = "{5940675A-B579-460E-94D1-54222C63F5DA}"
    tbl.tblPr.append(style)

    HEAD = RGBColor(0x1F, 0x2A, 0x44)
    ALT = RGBColor(0xF4, 0xF5, 0xF7)
    MINE = RGBColor(0xE7, 0xF3, 0xEA)

    for r, row in enumerate(rows):
        table.rows[r].height = Inches(0.30 if r == 0 else 0.26)
        for c, val in enumerate(row):
            cell = table.cell(r, c)
            cell.fill.solid()
            if r == 0:
                cell.fill.fore_color.rgb = HEAD
            elif r == len(rows) - 1:
                cell.fill.fore_color.rgb = MINE
            else:
                cell.fill.fore_color.rgb = ALT if r % 2 else RGBColor(0xFF, 0xFF, 0xFF)
            cell.text = val
            cell.margin_left = Emu(20000)
            cell.margin_right = Emu(20000)
            cell.margin_top = Emu(9000)
            cell.margin_bottom = Emu(9000)
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
                for run in p.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(7.5 if r == 0 else 8.5)
                    run.font.bold = (r == 0 or r == len(rows) - 1 or c == 0)
                    if r == 0:
                        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                    elif colour_cells and val.startswith("Y"):
                        run.font.color.rgb = RGBColor(0x1B, 0x7F, 0x3B)
                    elif colour_cells and val.startswith("N") and c > 0:
                        run.font.color.rgb = RGBColor(0xB0, 0x2A, 0x2A)
                    else:
                        run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)

    box = slide.shapes.add_textbox(Inches(0.12), Inches(caption_top), Inches(4.80), Inches(1.0))
    tf = box.text_frame
    tf.word_wrap = True
    for i, (lead, rest_text) in enumerate(caption):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        for text, bold in ((lead, True), (rest_text, False)):
            if not text:
                continue
            run = p.add_run()
            run.text = text
            run.font.bold = bold
            run.font.size = Pt(9)
            run.font.name = "Times New Roman"
    return slide


def check_overflow(prs) -> list[str]:
    """Measured, not guessed: flag any body box whose text will not fit."""
    problems = []
    for i, s in enumerate(prs.slides):
        sh = shape_by_name(s, BODY)
        if sh is None:
            continue
        sizes = [r.font.size.pt for para in sh.text_frame.paragraphs
                 for r in para.runs if r.font.size]
        if not sizes:
            continue
        fs = max(sizes)
        cpl = BOX_W_IN / (0.46 * fs / 72)
        avail = BOX_H_IN / (1.2 * fs / 72)
        used = sum(max(1, math.ceil(len(p.text) / cpl))
                   for p in sh.text_frame.paragraphs if p.text.strip())
        if used > avail - 1:
            problems.append(f"slide {i + 1} ({fs}pt): {used:.0f} lines, {avail:.0f} fit")
    return problems


def main():
    prs = Presentation(str(SRC))
    proto_text = prs.slides[2]
    proto_diag = prs.slides[9]
    text_el = [copy.deepcopy(sh._element) for sh in proto_text.shapes]
    diag_el = [copy.deepcopy(sh._element) for sh in proto_diag.shapes]
    layout_text, layout_diag = proto_text.slide_layout, proto_diag.slide_layout
    title_slide = prs.slides[0]

    for i in range(len(prs.slides) - 1, 0, -1):
        delete_slide(prs, i)

    set_plain(shape_by_name(title_slide, "Google Shape;62;p7"),
              "PERCH — A Personal AI Agent for the Desktop")
    sub = shape_by_name(title_slide, "object 7")
    for j, p in enumerate(sub.text_frame.paragraphs):
        para_set(p._p, [(SUB if j == 0 else "A Final Year Project", j == 0)])
    set_plain(shape_by_name(title_slide, BRAND), "PERCH")

    total = len(SLIDES) + 2
    ARCH_AFTER = "The Positioning Table - The Empty Row"

    for spec in SLIDES:
        if spec["kind"] == "table_position":
            s = clone(prs, layout_text, text_el)
            add_table_slide(prs, s, spec["title"], POSITION_ROWS, POSITION_CAPTION,
                            col0_w=1.06, table_top=0.50, caption_top=2.45, total=total)
        elif spec["kind"] == "table_ablation":
            s = clone(prs, layout_text, text_el)
            add_table_slide(prs, s, spec["title"], ABLATION_ROWS, ABLATION_CAPTION,
                            col0_w=2.30, table_top=0.50, caption_top=1.70, total=total,
                            colour_cells=False)
        else:
            s = clone(prs, layout_text, text_el)
            set_plain(shape_by_name(s, TITLE), spec["title"])
            set_body(s, spec["bullets"], spec["size"])
            set_plain(shape_by_name(s, BRAND), "PERCH")
            fix_pagenum(s, total)

        if spec["title"] == ARCH_AFTER:
            d = clone(prs, layout_diag, diag_el)
            set_plain(shape_by_name(d, DIAG_TITLE), ARCH_TITLE)
            set_plain(shape_by_name(d, BRAND), "PERCH")
            fix_pagenum(d, total, DIAG_PAGENUM)
            boxes = sorted((sh for sh in d.shapes if sh.name.startswith("Rounded Rectangle")),
                           key=lambda sh: sh.top)
            for sh, text in zip(boxes, ARCH_BOXES):
                head, _, tail = text.partition("   ")
                para_set(sh.text_frame.paragraphs[0]._p, [(head + "   ", True), (tail, False)])
            note = shape_by_name(d, "TextBox 201")
            if note is not None:
                tf = note.text_frame
                proto_p = copy.deepcopy(tf.paragraphs[0]._p)
                for p in list(tf._txBody.findall(A + "p")):
                    tf._txBody.remove(p)
                for line in ARCH_NOTE:
                    p = copy.deepcopy(proto_p)
                    para_set(p, [(line or " ", line.endswith("contribution."))])
                    tf._txBody.append(p)

    real = len(prs.slides._sldIdLst)
    for n, s in enumerate(prs.slides, start=1):
        fix_pagenum(s, real, PAGENUM, n)
        fix_pagenum(s, real, DIAG_PAGENUM, n)
        fix_pagenum(s, real, "Google Shape;73;p7", n)

    problems = check_overflow(prs)
    prs.save(str(OUT))
    print(f"wrote {OUT}  ({real} slides)")
    if problems:
        print("OVERFLOW:")
        for p in problems:
            print("  " + p)
    else:
        print("no overflow")


if __name__ == "__main__":
    main()
