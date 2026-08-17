"""
Build PERCH_Project_Review.pptx from the SENTINEL deck as a template.

The SENTINEL deck is a Google-Slides export of the college template, so all branding
(header bar, footer strip, logo, Times New Roman at 11.5pt) lives in the slide shapes
themselves rather than in the master. So we do not try to rebuild the template: we keep
the title slide, clone the content slide and the flow-diagram slide as prototypes, and
rewrite every string inside them. Formatting is inherited by construction.

    pip install python-pptx
    python docs/build_deck.py

The template lives outside this repo (it belongs to the previous project), so override
its location with PERCH_DECK_TEMPLATE if you have moved things around.
"""

from __future__ import annotations

import copy
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


# --------------------------------------------------------------------------- helpers

def para_set(p, pieces, size=None):
    """Rewrite a paragraph as [(text, bold), ...], reusing run 0 for formatting."""
    runs = p.findall(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}r"
    )
    if not runs:
        return
    proto = copy.deepcopy(runs[0])
    for r in runs:
        p.remove(r)
    # drop any endParaRPr leftovers that would re-add a trailing style mismatch
    for text, bold in pieces:
        r = copy.deepcopy(proto)
        rPr = r.find("{http://schemas.openxmlformats.org/drawingml/2006/main}rPr")
        if rPr is not None:
            rPr.set("b", "1" if bold else "0")
            if size is not None:
                rPr.set("sz", str(int(size * 100)))
        t = r.find("{http://schemas.openxmlformats.org/drawingml/2006/main}t")
        t.text = text
        p.append(r)


def shape_by_name(slide, name):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    return None


def set_plain(shape, text, bold=False, size=None):
    p = shape.text_frame.paragraphs[0]._p
    para_set(p, [(text, bold)], size)


def set_body(slide, bullets, size=None):
    """bullets: list of (bold_lead, rest). Empty tuple -> blank spacer line."""
    sh = shape_by_name(slide, BODY)
    tf = sh.text_frame
    paras = tf.paragraphs
    proto = copy.deepcopy(paras[0]._p)
    txBody = tf._txBody
    for p in list(txBody.findall("{http://schemas.openxmlformats.org/drawingml/2006/main}p")):
        txBody.remove(p)
    for item in bullets:
        p = copy.deepcopy(proto)
        if not item or (len(item) == 2 and not item[0] and not item[1]):
            para_set(p, [(" ", False)], size)
        else:
            lead, rest = item
            pieces = []
            if lead:
                pieces.append((lead, True))
            if rest:
                pieces.append((rest, False))
            para_set(p, pieces, size)
        txBody.append(p)


A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def fix_pagenum(slide, total, name=PAGENUM, index=None):
    """Update the ' / N' suffix, and cache the right number in the slidenum field."""
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
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    rId = slides[index].get(
        "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    )
    prs.part.drop_rel(rId)
    xml_slides.remove(slides[index])


def clone(prs, layout, proto_elements):
    """Add a new slide carrying shape-level copies of a prototype slide."""
    new = prs.slides.add_slide(layout)
    for sh in list(new.shapes):
        sh._element.getparent().remove(sh._element)
    tree = new.shapes._spTree
    for el in proto_elements:
        tree.append(copy.deepcopy(el))
    return new


# --------------------------------------------------------------------------- content

SUB = "A Personal AI Agent That Lives Where Your Desktop Lives, Not Inside an Application"

SLIDES = []


def S(title, bullets, size=None):
    SLIDES.append({"kind": "text", "title": title, "bullets": bullets, "size": size})


S("Outline", [
    ("Introduction", " - Nobody Uses One AI Any More"),
    ("Problem Statement", " - Your Context Is Trapped Per-Vendor"),
    ("Evidence", " - Measured Failure, Market Data, Expensive Precedents"),
    ("Scope & Objectives", ""),
    ("Existing Work", " - Highlight AI, Click to Do, and the Mac-Only Wall"),
    ("System Architecture", " - Four Layers, One Request Path"),
    ("Layer 1", " - The OS Surface, and Why It Is Already Proven"),
    ("Layer 2", " - Context Assembly Under a Token Budget"),
    ("Layer 3", " - Memory the User Writes, Owns and Can Export"),
    ("Layer 4", " - Execution, Model Choice and the Cost Floor"),
    ("Private Mode", " - Declared, Never Inferred"),
    ("Technologies, Benchmarks and Evaluation Plan", ""),
    ("Base Paper, The Gap, Expected Results", ""),
    ("Conclusion and References", ""),
])

S("Introduction - Nobody Uses One AI Any More", [
    ("The situation:", " A typical user now runs ChatGPT for general questions, Claude Code or "
     "Copilot for programming, Perplexity for research, and Gemini inside Docs."),
    ("The consequence:", " Each one holds a separate, private memory of you. None of them can see "
     "the others. Your context is fragmented across the vendors you pay."),
    ("It is expensive:", " a power user pays $70-110/month across four subscriptions, and still "
     "loses 15-30 minutes of context on every platform switch."),
    ("It is not settling down:", " ChatGPT's assistant market share fell from ~60% in early 2025 to "
     "under 45% by Q1 2026. People are moving constantly, and the context does not move with them."),
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
    ("The knowledge already existed.", " It was simply locked inside a session, in a product that "
     "will never share it. That is the problem PERCH exists to remove."),
])

S("Problem Statement", [
    ("The vulnerability, in one sentence:", " every assistant's memory of you is owned by the vendor "
     "of that assistant, so personal context cannot follow you across the tools you actually use."),
    ("This is measurable, not rhetorical.", " PAUSE (ACM SIGKDD 2026) found that state-of-the-art "
     "proprietary models fail to reach 70% task completion on scenarios requiring stateful reasoning "
     "and configuration awareness."),
    ("Read that carefully:", " the failure is not the model's reasoning. The failure is the state "
     "around the model - persistent knowledge of who the user is, what they are working on, and what "
     "constraints they operate under."),
    ("The second half of the problem is location.", " Every assistant is a destination. You leave "
     "your document, your IDE or your PDF, go to a window, paste, read, and carry the answer back."),
    ("So the problem statement is two-part:", " personal context is trapped per-vendor, and the "
     "assistant that would use it is trapped inside an application."),
])

S("Proof This Is Real - Measured, Not Asserted", [
    ("ACM measurement.", " PAUSE, KDD 2026: frontier models below 70% task completion when the task "
     "requires reasoning over persistent user state. An ACM 2026 number, not a blog claim."),
    ("Established research category.", " Personal LLM Agents (Tsinghua AIR) defines agents deeply "
     "integrated with personal data and personal devices, and names context sensing and memorization "
     "as fundamental unsolved capabilities."),
    ("Market behaviour.", " $70-110/month across four assistants; 15-30 minutes lost per switch; "
     "market share moving 15 points in a year."),
    ("Incumbent behaviour.", " Highlight AI raised $50M for exactly this position and pivoted to "
     "enterprise team tooling in March 2026. The individual user is no longer their product."),
    ("Capability now exists that did not in 2024.", " Qwen3 4B runs in ~3 GB and Qwen3 8B in ~5-6 GB "
     "quantised. A genuinely useful local model now fits on an ordinary student laptop."),
])

S("Why This Position Is Open - and Stays Open", [
    ("A neutral context layer is against every incumbent's business model.", " OpenAI wants you "
     "inside ChatGPT. Google wants you inside Gemini. Microsoft wants you inside Copilot. Apple wants "
     "you on a Mac."),
    ("A layer whose entire value is making all of your AIs know you can only be built by someone "
     "with no model to sell.", " That is the structural reason the position is empty."),
    ("The one company that tried it left.", " Highlight AI, $50M and 500,000+ users, repositioned in "
     "March 2026 as a shared intelligence layer for teams - meeting preparation, attendee insights, "
     "decision summaries."),
    ("Microsoft is building the same primitive but gating it.", " Windows 11 Click to Do performs AI "
     "actions on selected screen content, but requires a Copilot+ PC with a dedicated NPU. Most "
     "laptops in India do not have one."),
    ("We are not claiming nobody thought of this.", " We are claiming nobody with a model to sell can "
     "afford to build it, and the one neutral player walked away from individual users."),
])

S("What the Expensive Failures Taught Us", [
    ("Humane AI Pin:", " raised $230M, shipped fewer than 10,000 units, sold to HP for $116M."),
    ("Rabbit R1:", " sold 100,000 units, then took mass returns."),
    ("Rewind AI:", " acquired by Meta as Limitless; the Mac app shut down 19 December 2025 and EU/UK "
     "access was cut immediately."),
    ("Microsoft Recall:", " audits found an admin-rights attacker could exfiltrate the database; "
     "Microsoft began cutting back Copilot across Windows after user backlash in early 2026."),
    ("The published lesson, verbatim:", " \"AI doesn't need a new gadget - it needs to improve the "
     "tools you already use.\""),
    ("Every stated cause maps to a design decision.", " No hardware. One primitive, not four. No "
     "destination - it appears where you are. Summoned only, never always-on capture. Opt-in by "
     "definition, because it is a shortcut you press."),
])

S("Scope & Objectives", [
    ("Scope:", " PERCH is a desktop-resident personal AI agent for Windows. It is dormant in the "
     "background, summoned by a selection, a screenshot or a shortcut in any application, answers in "
     "a slim panel beside your work, and writes the answer back into the document you were in."),
    ("O1 - Surface.", " Three triggers, panel placement beside the host window without stealing "
     "focus, and edit-in-place with no per-application plugin."),
    ("O2 - Context assembly.", " Decide what enters the prompt under a hard ceiling set by whichever "
     "model is selected, from a 4B local model to a frontier API."),
    ("O3 - Memory.", " User-authored, structured, portable personal context - stored as files the "
     "user can open, edit, export or delete."),
    ("O4 - Execution.", " Model-agnostic routing across local Ollama, free cloud tiers and the "
     "user's own key, with a private mode that provably sends nothing."),
    ("Out of scope, and named as such:", " adaptive automatic model routing, multi-device sync, and "
     "app automation are all v2."),
])

S("Existing Work - Our Real Competition", [
    ("Highlight AI", " - $50M, 500,000+ users, Mac and Windows. Selection-triggered, screen-aware, "
     "local audio transcription. Cloud-dependent, rate-limited, no model choice, closed source, and "
     "pivoted to enterprise in March 2026."),
    ("Windows 11 Click to Do", " - the same primitive, from the OS vendor. Requires a Copilot+ PC "
     "NPU, offers a fixed menu of actions, and Microsoft is retreating from the Windows AI push."),
    ("Raycast AI ($8/mo), Apple Intelligence, Dottie, BoltAI", " - the entire \"best AI assistant\" "
     "review category is a Mac category. None of these run on Windows."),
    ("Jan.ai (5.3M downloads), AnythingLLM, Khoj, PyGPT, Chatbox", " - right philosophy, wrong shape. "
     "All local-capable, all open, and every one of them is an application window you open."),
    ("The pattern:", " tools that are OS-integrated are closed, cloud-only or hardware-gated. Tools "
     "that are local and open are destinations you have to visit."),
])

S("The Positioning Table - The Empty Row", [], None)
SLIDES[-1]["kind"] = "table"

S("Layer 1 - Three Triggers, Two Capture Paths", [
    ("T1 - Global hotkey.", " Win32 RegisterHotKey gives a system-wide shortcut that fires regardless "
     "of which application has focus. Rust: tauri-plugin-global-shortcut, a first-party Tauri v2 plugin."),
    ("T2 - Read the current selection. This is the hard one, so it has two paths.", ""),
    ("Path A - UI Automation.", " GetFocusedElement, then TextPattern, then GetSelection, then "
     "GetText. This is the documented Windows accessibility framework that exists so screen readers "
     "can do exactly this. It is the supported path, not a hack."),
    ("Path B - clipboard round-trip.", " Save the user's clipboard, send Ctrl+C, read the selection, "
     "restore the original clipboard. Less elegant, works essentially everywhere."),
    ("Design rule:", " try A, fall back to B, and log which one worked per application. That per-app "
     "coverage table is a deliverable - no competitor publishes one."),
    ("T3 - Screenshot.", " Transparent full-screen overlay, drag a region, capture the pixels, "
     "optional OCR. The same mechanism every screenshot tool uses."),
], size=10.5)

S("Layer 1 - Edit In Place, and Why There Is No Plugin", [
    ("This is the capability that separates PERCH from a chat window.", " A chat window can only ever "
     "hand you text to copy. PERCH writes the answer back into the application you came from."),
    ("The mechanism:", " put the answer on the clipboard, restore focus to the original window using "
     "the HWND saved at trigger time, send Ctrl+V, then restore the user's previous clipboard."),
    ("Why replacement works with no app-specific integration:", " in every text field on Windows, "
     "pasting while text is selected replaces that text. We are using behaviour every text field "
     "already has."),
    ("Three actions, the user's choice:", " Replace overwrites the selection, Insert after appends "
     "below it, Copy only changes nothing."),
    ("Rejected alternative - per-application plugins.", " An Office add-in, a VS Code extension and a "
     "browser extension give better fidelity, but mean N integrations, N review processes, and it "
     "only ever works where we shipped. The clipboard path works everywhere on day one."),
], size=10.5)

S("Phase 0 - The OS Layer Is Already Built and Working", [
    ("We built the risky layer first, before designing the product.", " The application and agent "
     "layers are familiar work. The open question was whether a desktop app can genuinely reach into "
     "other applications. It can, and here is the running code."),
    ("T1 verified:", " a system-wide hotkey fires regardless of focus (RegisterHotKey + message loop)."),
    ("T2 verified:", " selection read from other applications - UI Automation available and working, "
     "clipboard round-trip as fallback, with the method logged per application."),
    ("T3 verified:", " region screenshot via overlay and capture."),
    ("Panel placement verified:", " GetForegroundWindow + GetWindowRect correctly returned the host "
     "window and its rectangle; the panel docks beside it, falling back left, then to the screen edge."),
    ("Edit-in-place verified:", " focus restore and paste-back, with a deliberate refusal to paste if "
     "Windows blocks the focus change - landing in the wrong window is worse than not pasting."),
    ("Nothing here needs a driver, a kernel hook, an OS modification or a special permission.", ""),
], size=10)

S("Layer 2 - Context Assembly Under a Token Budget", [
    ("The job:", " given a question, a selection, and everything known about the user, decide what "
     "actually enters the prompt, under a hard ceiling set by the chosen model."),
    ("budget = context_window(model) - reserve(response) - reserve(system)", ""),
    ("Priority order:", " system and persona, always; the selection, always, because it is why the "
     "user summoned us; recent conversation, oldest truncated first; then retrieved memory into "
     "whatever remains; tool results claimed from that same allowance."),
    ("Memory items enter whole or not at all.", " Half a project description is worse than none."),
    ("This is what makes model choice possible.", " Swap a local Qwen3 4B for a frontier API and the "
     "budget recomputes - nothing else changes. The same memory layer serves a 3 GB local model and a "
     "200K-context frontier model."),
    ("Relevance uses three signals:", " semantic similarity to the query and selection, structural "
     "match (a project block is relevant to a coding question, not to a leave email), and recency of use."),
], size=10.5)

S("Layer 3 - Memory the User Writes and Owns", [
    ("Four kinds.", " Identity - who you are and how you want answers written. Domain - projects, "
     "courses, ongoing work. Episodic - past conversations and outcomes. Working - this session."),
    ("Identity and Domain are written by you.", " That is the deliberate inversion: personal context "
     "is authored and owned, not silently inferred from conversation."),
    ("The pipeline:", " store text with category, embedding, timestamps and use count; index in a "
     "local vector index; retrieve by category filter, then semantic top-k, then recency and use "
     "rerank, then budget-aware selection. SQLite and plain files. No server."),
    ("Every memory item is a file you can open, edit or delete.", " Memory you cannot read is memory "
     "you cannot trust - and after Recall, that is not a slogan."),
    ("Categories are extensible:", " academic conventions, writing style, professional context, "
     "accessibility constraints, and user-defined categories with user-defined schemas."),
], size=10.5)

S("Layer 3 - Importing What Is Stranded in Your Other AIs", [
    ("This is the mechanism that solves the problem statement, and the feature that makes people "
     "install it.", ""),
    ("PERCH ships extraction prompts.", " You paste one into any assistant session that already "
     "contains knowledge about you, and it returns a structured block you import in one click."),
    ("The Project block captures:", " name and one-line purpose; stack, tools and versions; "
     "architecture decisions and why each was chosen; problems hit and how each was resolved; "
     "timeline; results and benchmarks; what remains and known limitations."),
    ("Run it once at the end of a project inside a coding assistant, and every one of those facts is "
     "permanently yours, outside that tool.", ""),
    ("The adoption move:", " every competitor says switch to us. PERCH says keep everything you are "
     "paying for - and we will make all of it know who you are. PERCH can emit a context block you "
     "paste into ChatGPT, Claude or Cursor, so that assistant knows your project and constraints."),
    ("The more AI tools you use, the more useful PERCH becomes.", ""),
], size=10)

S("Where It Pays Off - Worked Examples", [
    ("Filling an application form", " - \"describe a technical challenge you overcame in 200 words\". "
     "Select the field and ask. The project block already holds the challenge, the fix and the "
     "result, and it writes to the word limit in your tone."),
    ("Updating a resume", " - the results and numbers are already stored, so it produces bullets and "
     "you pick one, instead of hunting for where you recorded the metric."),
    ("Interview preparation", " - ask for the three hardest problems across all your projects. It has "
     "them, because you imported them, rather than scrolling months of chat history across two tools."),
    ("Emailing a professor about your project", " - trigger inside the compose window. Project from "
     "domain memory, tone and college from identity memory. The draft is correct first time."),
    ("Starting a project that resembles an old one", " - it surfaces the earlier decision and the "
     "reason you made it."),
    ("The pattern in all five:", " the knowledge already existed - it was locked in a session inside "
     "a product that will never share it."),
], size=10.5)

S("Private Mode - Declared, Never Inferred", [
    ("Classification is the wrong answer here, and we will not pretend otherwise.", " Deciding what "
     "is private from the content itself means a classifier whose false-negative cost is leaking a "
     "company secret to a cloud API. No accuracy figure makes that acceptable."),
    ("PERCH does not guess. Privacy is a user-declared policy, in three forms.", ""),
    ("1. Per-request toggle.", " A Private switch on the panel. Flip it and the request goes to the "
     "local model. Visible before you send, on every request."),
    ("2. Source rules - the useful one.", " Declare a source private once: this application, this "
     "folder, or this window-title pattern. PERCH knows the source at capture time, so it never needs "
     "to understand the text, only where it came from. Deterministic, auditable, no model involved."),
    ("3. Global default.", " Set local as the default and escalate to cloud explicitly. For anyone "
     "handling regulated data this is the only sane setting."),
    ("The demonstrable claim:", " in private mode, zero bytes leave the machine - provable with a "
     "packet capture, which is a better privacy demonstration than any policy page."),
], size=10),

S("Layer 4 - Execution, Model Choice and the Cost Floor", [
    ("Model registry.", " Each entry holds provider, endpoint, model id, context window, tool support "
     "and whether it is local. Everything upstream reads context_window from here, which is what makes "
     "Layer 2 model-agnostic."),
    ("Ollama, local", " - free, open source, no rate limit on localhost:11434. Qwen3 4B in ~3 GB."),
    ("NVIDIA NIM", " - free API key with the Developer Program, no credit card, 100+ models, a "
     "practical community baseline of ~40 requests per minute."),
    ("Your own key, or OpenRouter BYOK", " - whatever you already pay for."),
    ("A student can run PERCH for zero rupees.", " Fully local, or on a free tier, or with their own "
     "key. That is the one thing a $50M-funded competitor structurally cannot match."),
    ("Tools:", " web search and fetch, local file read, OCR and clipboard write - declared only when "
     "the selected model supports tool calling, and charged against the same token budget."),
    ("Automatic adaptive routing is explicitly v2.", " The user chooses; switching is one click."),
], size=10),

S("Technologies Used", [
    ("Shell - Tauri v2.", " 30-50 MB idle against Electron's 150-300 MB, and a sub-10 MB installer "
     "against 100 MB+. PERCH is always running, so a background assistant that idles at 250 MB is one "
     "users uninstall. Hoppscotch's migration went 165 MB to 8 MB with a 70% memory reduction."),
    ("Core - Rust.", " Hotkeys, UI Automation, clipboard, window management and tray. Verified "
     "bindings: tauri-plugin-global-shortcut, the uiautomation crate, arboard, and the official "
     "windows crate."),
    ("Interface - React and TypeScript.", " Fast iteration on the surface, which is what gets judged."),
    ("AI/ML - Python sidecar.", " Embeddings, retrieval and budget assembly - the ML work, in the "
     "language the team already knows."),
    ("Storage - SQLite and plain files.", " No server, inspectable, portable."),
    ("Local inference - Ollama.", " Free, no rate limit."),
], size=10.5)

S("Datasets and Benchmarks", [
    ("LongMemEval", " - 500 questions across 6 categories: single-session user recall, assistant "
     "recall, preference recall, knowledge update, temporal reasoning and multi-session recall. Tests "
     "extraction, multi-session reasoning, temporal reasoning, knowledge updates and abstention."),
    ("LoCoMo", " - 1,540 questions across 4 categories (single-hop, multi-hop, open-domain, "
     "temporal), roughly 300 turns and up to 35 sessions per conversation."),
    ("PersonaMem, PerLTQA, DialSim, BEAM", " - personalised memory, covering explicit facts and "
     "implicit preferences."),
    ("Honest framing, stated up front:", " 2026 reference scores are LoCoMo 92.5% and LongMemEval "
     "94.4%. These are near-saturated. We do not pitch beating them - we use them to validate that "
     "our memory layer is competent, and we report honestly."),
    ("BEAM-1M at 62% is the honest headroom", ", and the practitioner consensus is that no single "
     "evaluation fully characterises production memory performance."),
], size=10.5)

S("Evaluation Plan", [
    ("E1 - Memory retrieval quality.", " LongMemEval and LoCoMo, reported honestly against published "
     "2026 baselines. Demonstrates competence, claims no record."),
    ("E2 - Context assembly ablation. This is the one nobody else publishes.", " Three conditions - "
     "no memory, full profile always injected, and budget-aware selection - measured at three model "
     "sizes. Nobody else has to serve a 4B local model and a frontier API from one memory layer, so "
     "nobody else has a reason to run this experiment."),
    ("E3 - Latency.", " Trigger to first token, local versus cloud, measured."),
    ("E4 - Private mode.", " Bytes leaving the machine must be zero, proved by packet capture."),
    ("E5 - UI Automation coverage per application.", " A measured table across common Windows "
     "applications, documenting where Path A works and where the clipboard fallback carries it. No "
     "competitor publishes one."),
], size=10.5)

S("Base Paper - PAUSE, ACM SIGKDD 2026", [
    ("PAUSE: A User-Centric Benchmark for Personal AI Assistants in Unified Service Environments.",
     " ACM SIGKDD 2026, 9-13 August 2026, Jeju Island."),
    ("Why this is the base paper:", " it is ACM and 2026, its subject is literally personal AI "
     "assistants, and its definition is our specification - an assistant must reason over persistent "
     "user state, respect user-specific configurations and permissions, and sustain long-horizon, "
     "constraint-aware interactions."),
    ("It evaluates three dimensions", " - stateful reasoning, multi-service coordination, and "
     "user-coupled interaction. The first and third are exactly what PERCH is built around."),
    ("And it hands us the gap, quantified:", " state-of-the-art proprietary models fail to reach 70% "
     "task completion on scenarios requiring stateful reasoning and configuration awareness."),
    ("Conceptual anchor:", " Personal LLM Agents (Tsinghua AIR) supplies the taxonomy - fundamental "
     "capabilities including context sensing and memorization, efficiency, and security - which maps "
     "onto our four layers almost one-to-one."),
], size=10.5)

S("The Gap - Where PAUSE Stops and We Begin", [
    ("PAUSE is a benchmark, not a system.", " It measures assistants inside unified service "
     "environments that are assumed to already have access and configuration."),
    ("It does not address how a user supplies their own state.", " We do - user-authored memory plus "
     "extraction prompts that recover what is stranded in other assistants."),
    ("It does not address OS-level capture.", " We do - three triggers, two capture paths, and "
     "edit-in-place with no per-application plugin."),
    ("It does not address operating within a fixed token budget across heterogeneous models.", " We "
     "do - that is Layer 2, and it is what lets one memory layer serve a 3 GB local model and a "
     "frontier API."),
    ("Stated in one line for the panel:", " our base paper is a KDD 2026 benchmark for personal AI "
     "assistants which found that even frontier models fall below 70% when a task requires knowing "
     "the user's state. We build the assistant that fixes that, on the desktop."),
], size=10.5)

S("Expected Results and Honest Limitations", [
    ("What we expect to show.", " Budget-aware assembly beating both naive conditions at every model "
     "size, with the largest margin on the smallest model - because that is where the budget actually "
     "binds. Sub-second trigger-to-first-token locally. Zero bytes in private mode."),
    ("What we do not claim.", " We did not invent selection-triggered AI - Highlight and Click to Do "
     "exist. We did not invent agent memory - Mem0, Zep and Letta are mature. We will not beat "
     "LoCoMo or LongMemEval, which are near-saturated. We are not proposing a novel retrieval algorithm."),
    ("What we do claim.", " The first open-source, model-agnostic, OS-integrated personal assistant "
     "that runs fully local on ordinary hardware; user-authored portable memory; token-budget-aware "
     "context assembly across heterogeneous models; and an honest component evaluation with latency "
     "and privacy measurements nobody publishes for a real assistant workload."),
    ("Known limitations.", " UI Automation coverage varies by application, which is why the clipboard "
     "fallback exists and why coverage is a documented deliverable. Screen-reading behaviour can trip "
     "antivirus heuristics, so the installer must be signed and all capture must stay user-initiated."),
], size=10)

S("Conclusion", [
    ("The problem is not which AI you use.", " It is that your context is trapped inside whichever one "
     "you happened to type it into, and that the assistant which would use it is trapped inside an "
     "application window."),
    ("The measurement backs it.", " ACM SIGKDD 2026 found frontier models below 70% when a task needs "
     "persistent knowledge of the user."),
    ("PERCH is the layer above the applications.", " Summoned anywhere in Windows, answers beside your "
     "work, writes back into the document you were in, remembers what you told it once, and runs on "
     "whichever model you choose - including one that never leaves your machine."),
    ("The risky part is already done.", " Phase 0 proves the OS layer with running code: three "
     "triggers, panel placement, and edit-in-place, using only documented user-mode APIs."),
    ("The technical core is Layers 2 and 3", " - embeddings, retrieval, ranking and budget "
     "optimisation, evaluated on public benchmarks with an ablation nobody else has a reason to run."),
    ("You pay for four AI assistants. None of them know you. PERCH is the one that does - and it "
     "works inside all of them.", ""),
], size=10)

S("References", [
    ("[1] PAUSE: A User-Centric Benchmark for Personal AI Assistants in Unified Service Environments.",
     " ACM SIGKDD 2026 (KDD '26), Jeju Island. - BASE PAPER"),
    ("[2] Li et al.", " Personal LLM Agents: Insights and Survey about the Capability, Efficiency and "
     "Security. Institute for AI Industry Research, Tsinghua University."),
    ("[3] A Survey on the Memory Mechanism of LLM-based Agents.", " ACM TOIS Vol 43(6), 2025, DOI "
     "10.1145/3748302. - cited for Layer 3 only"),
    ("[4] Bridging Intuitive Associations and Deliberate Recall: Empowering LLM Personal Assistant "
     "with Graph-Structured Long-term Memory.", " Findings of ACL 2025."),
    ("[5] Memory in the LLM Era: Modular Architectures and Strategies in a Unified Framework.", " VLDB 2026."),
    ("[6] From Generic Intelligence to Personalized AI: Foundations of LLM Personalization.",
     " Tutorial, ACM SIGKDD 2026."),
    ("[7] LongMemEval", " - long-term memory benchmark, 500 questions, 6 categories."),
    ("[8] LoCoMo", " - long conversational memory benchmark, 1,540 questions, up to 35 sessions."),
    ("[9] Microsoft.", " UI Automation Overview and IUIAutomationElement, Windows Accessibility "
     "documentation."),
    ("[10] Tauri v2", " documentation - window management, global shortcut plugin, transparency."),
], size=9.5)


# Slides whose measured line count came too close to the 3.3in body height get
# stepped down a size. Measured, not guessed - see the overflow check.
TIGHTEN = {
    "Problem Statement": 10.5,
    "Why This Position Is Open - and Stays Open": 10.5,
    "Scope & Objectives": 10.5,
    "Layer 1 - Three Triggers, Two Capture Paths": 10.0,
    "Base Paper - PAUSE, ACM SIGKDD 2026": 10.0,
    "References": 9.0,
}
for _spec in SLIDES:
    if _spec["title"] in TIGHTEN:
        _spec["size"] = TIGHTEN[_spec["title"]]


# ------------------------------------------------------------- architecture diagram

ARCH_TITLE = "System Architecture - Four Layers, One Request Path"
ARCH_BOXES = [
    "USER   working in any Windows application - PDF, IDE, browser, email, form",
    "TRIGGER   L1   hotkey, selection or screenshot - nothing is read until you press it",
    "CAPTURE   L1   UI Automation, clipboard fallback; the host window handle is saved",
    "BUDGET   L2   budget = context_window(model) - reserve(response) - reserve(system)",
    "RETRIEVE   L3   category filter -> semantic top-k -> recency rerank -> whole items only",
    "ASSEMBLE   L2   system, selection, conversation, memory - strict priority order",
    "ROUTE   L4   local Ollama - free cloud tier - your own key.  Private always means local",
    "PRESENT   L1   the answer streams into a slim panel beside your work, never over it",
    "EDIT IN PLACE   L1   Replace / Insert after / Copy - back into the app you came from",
]
ARCH_NOTE = [
    "L2 and L3 are the contribution.",
    "",
    "L1 is already built and proven - see Phase 0.",
    "",
    "L4 is what makes it free.",
]


# --------------------------------------------------------------------------- build

def main():
    prs = Presentation(str(SRC))

    proto_text = prs.slides[2]
    proto_diag = prs.slides[9]
    proto_text_el = [copy.deepcopy(sh._element) for sh in proto_text.shapes]
    proto_diag_el = [copy.deepcopy(sh._element) for sh in proto_diag.shapes]
    layout_text = proto_text.slide_layout
    layout_diag = proto_diag.slide_layout

    title_slide = prs.slides[0]

    # strip everything except the title slide
    for i in range(len(prs.slides) - 1, 0, -1):
        delete_slide(prs, i)

    # ---- title slide
    set_plain(shape_by_name(title_slide, "Google Shape;62;p7"),
              "PERCH \u2014 A Personal AI Agent for the Desktop")
    sub = shape_by_name(title_slide, "object 7")
    for j, p in enumerate(sub.text_frame.paragraphs):
        if j == 0:
            para_set(p._p, [(SUB, True)])
        else:
            para_set(p._p, [("A Final Year Project", False)])
    set_plain(shape_by_name(title_slide, BRAND), "PERCH")

    total = len(SLIDES) + 2  # +title +architecture

    def add_text_slide(spec):
        s = clone(prs, layout_text, proto_text_el)
        set_plain(shape_by_name(s, TITLE), spec["title"])
        set_body(s, spec["bullets"], spec["size"])
        set_plain(shape_by_name(s, BRAND), "PERCH")
        fix_pagenum(s, total)
        return s

    def add_arch_slide():
        s = clone(prs, layout_diag, proto_diag_el)
        set_plain(shape_by_name(s, DIAG_TITLE), ARCH_TITLE)
        set_plain(shape_by_name(s, BRAND), "PERCH")
        fix_pagenum(s, total, DIAG_PAGENUM)

        boxes = [sh for sh in s.shapes
                 if sh.name.startswith("Rounded Rectangle")]
        boxes.sort(key=lambda sh: sh.top)
        for sh, text in zip(boxes, ARCH_BOXES):
            head, _, tail = text.partition("   ")
            p = sh.text_frame.paragraphs[0]._p
            para_set(p, [(head + "   ", True), (tail, False)])

        note = shape_by_name(s, "TextBox 201")
        if note is not None:
            tf = note.text_frame
            proto_p = copy.deepcopy(tf.paragraphs[0]._p)
            txBody = tf._txBody
            ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}p"
            for p in list(txBody.findall(ns)):
                txBody.remove(p)
            for line in ARCH_NOTE:
                p = copy.deepcopy(proto_p)
                para_set(p, [(line or " ", line.endswith("contribution."))])
                txBody.append(p)
        return s

    # slide order: outline, intro x2, problem, evidence x3, scope, existing, table,
    #              [architecture], L1 x3, L2, L3 x2, examples, private, L4, tech, ...
    ARCH_AFTER = "The Positioning Table - The Empty Row"

    for spec in SLIDES:
        if spec["kind"] == "table":
            add_positioning_slide(prs, clone(prs, layout_text, proto_text_el), total)
        else:
            add_text_slide(spec)
        if spec["title"] == ARCH_AFTER:
            add_arch_slide()

    # renumber the "/ N" suffix once the real count is known
    real = len(prs.slides._sldIdLst)
    for n, s in enumerate(prs.slides, start=1):
        fix_pagenum(s, real, PAGENUM, n)
        fix_pagenum(s, real, DIAG_PAGENUM, n)
        fix_pagenum(s, real, "Google Shape;73;p7", n)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"wrote {OUT}  ({real} slides)")


def add_positioning_slide(prs, s, total):
    set_plain(shape_by_name(s, TITLE), "The Positioning Table - The Empty Row")
    set_plain(shape_by_name(s, BRAND), "PERCH")
    fix_pagenum(s, total)

    body = shape_by_name(s, BODY)
    body._element.getparent().remove(body._element)

    rows = [
        ["", "Windows", "No special\nhardware", "Local\noption", "Cloud\nchoice", "Selection\ntriggered", "Individual\nuser", "Open\nsource"],
        ["Highlight AI", "Y", "Y", "N", "N", "Y", "N  pivoted", "N"],
        ["Click to Do", "Y", "N  NPU", "Y", "N", "Y", "Y", "N"],
        ["Raycast / Apple", "N", "-", "partial", "partial", "Y", "Y", "N"],
        ["Jan.ai / PyGPT / Khoj", "Y", "Y", "Y", "Y", "N", "Y", "Y"],
        ["PERCH", "Y", "Y", "Y", "Y", "Y", "Y", "Y"],
    ]

    left, top = Inches(0.12), Inches(0.55)
    width, height = Inches(4.80), Inches(1.9)
    gf = s.shapes.add_table(len(rows), len(rows[0]), left, top, width, height)
    table = gf.table
    table.columns[0].width = Inches(1.06)
    for c in range(1, 8):
        table.columns[c].width = Inches(0.534)

    # The default python-pptx table style is a banded accent theme that fights the
    # template. Force the plain grid and paint the fills ourselves.
    tbl = table._tbl
    tbl.tblPr.set("firstRow", "1")
    tbl.tblPr.set("bandRow", "0")
    for el in tbl.tblPr.findall(A + "tableStyleId"):
        tbl.tblPr.remove(el)
    style = tbl.tblPr.makeelement(A + "tableStyleId", {})
    style.text = "{5940675A-B579-460E-94D1-54222C63F5DA}"  # No Style, Table Grid
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
            cell.margin_left = Emu(18000)
            cell.margin_right = Emu(18000)
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
                    elif val.startswith("Y"):
                        run.font.color.rgb = RGBColor(0x1B, 0x7F, 0x3B)
                    elif val.startswith("N") and c > 0:
                        run.font.color.rgb = RGBColor(0xB0, 0x2A, 0x2A)
                    else:
                        run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)

    caption = s.shapes.add_textbox(Inches(0.12), Inches(2.62), Inches(4.80), Inches(0.9))
    tf = caption.text_frame
    tf.word_wrap = True
    lines = [
        ("Read the columns, not the rows.", " Every competitor fails at least one column that matters "
         "to an individual user on an ordinary Windows laptop."),
        ("Highlight is closed, cloud-only and has left this segment.", " Click to Do needs an NPU. "
         "The Mac tools do not run here. The local, open tools are all windows you have to go to."),
        ("The bottom row is the project.", " Nothing in it is individually novel - the combination is "
         "the one nobody is shipping."),
    ]
    for i, (lead, rest) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r1 = p.add_run(); r1.text = lead
        r1.font.bold = True; r1.font.size = Pt(9.5); r1.font.name = "Times New Roman"
        r2 = p.add_run(); r2.text = rest
        r2.font.bold = False; r2.font.size = Pt(9.5); r2.font.name = "Times New Roman"
    return s


if __name__ == "__main__":
    main()
