# PERCH — architecture diagram prompt (Gemini 3 Pro Image / "Nano Banana Pro")

**Why a prompt and not Mermaid.** The panel responded better to the coloured, icon-led architecture
diagrams other groups produced than to monochrome Mermaid. Nano Banana Pro renders legible in-image
text, which is the part most image models get wrong — so the prompt below **spells out every label
verbatim**, because anything you leave to the model comes back as plausible-looking gibberish.

**How to use it.** Paste **PROMPT 0** into Gemini with image generation — it is the current
recommendation, below. PROMPT 1 (further down) is the earlier layer-band version, kept as an
alternative structure rather than deleted. Use the follow-ups to fix whatever comes out wrong — Gemini
is much better at editing an existing image than at getting a dense diagram exactly right first time.
Ask for **16:9** and the highest resolution offered.

**⚠️ Why PROMPT 0 replaces PROMPT 1 as the recommendation.** Stacking four architectural *tiers* as
parallel bands groups components by where they live in the codebase — but privacy, routing, memory,
ranking, gating and packing all fire together for a *single request*, and splitting them across two
separate rows (the old "L2 context" / "L3 memory") hid that they are one coherent step, not two. PROMPT
0 groups by **what happens together**, not by implementation tier: four stage-clusters, each one its
own small wired sub-diagram with real component-to-component arrows inside it, chained left to right by
one thick arrow per handoff. Same fifteen-plus components, same edges — regrouped around the actual
work being done at each point in the request, which is also just a clearer story to tell out loud.

---

**What a good comparison diagram taught us.** A parallel project's title-approval diagram (a numbered
1–8 pipeline for a requirements-gap detector) did three things our first stage render did not, all worth
stealing:

| It did | We were missing it | Now fixed by |
|---|---|---|
| **Named real technologies on the diagram** — Neo4j, FAISS, PostgresDB, GitHub | Ours named almost none, so it read as a concept sketch rather than a built system | small monospace tech tags: `Win32 · UI Automation`, `Tauri v2`, `SQLite + sqlite-vec`, `nomic-embed-text`, `qwen2.5` |
| **Explicit input artifacts** — PDF, DOCX, Email, Jira as file icons feeding the left edge | Ours started at "user presses a key" with no visible inputs at all | an **input column**: where you work (PDF/IDE/browser/email) *and* where your context comes from |
| **Explicit output artifacts** — an interactive dashboard and a PDF/XLSX report | Ours ended at "Edit In Place" with no visible deliverable | an **output column**: the edited document, and the answer-plus-provenance panel |

> **The most valuable of the three is the input column.** Our import path — ChatGPT/Claude/Gemini
> exports parsed locally — is **contribution C3** and was completely invisible on the diagram. A panel
> looking at the old render could not tell that PERCH ingests anything at all.

**One thing deliberately not copied: the monochrome whiteboard aesthetic.** That diagram is hand-drawn
greyscale, which reads as considered and engineer-ish — but this panel explicitly asked for colour and
for database iconography. Our colour-coded stages are an advantage here, not a gap; keep them.

---

## ★★★ PROMPT 0 — RECOMMENDED: four connected stage-clusters

```
Create a professional software architecture diagram for a desktop AI application
called PERCH. Widescreen 16:9, high resolution, suitable for a university project
review slide.

THIS IS A FOUR-STAGE PIPELINE, READ LEFT TO RIGHT. Each stage is drawn as one
large, soft-filled, rounded rectangle "super-container" with a title header
band at its top. Inside each super-container are several small white icon
cards (nodes), connected to each other with visible arrows -- so each stage
is its own small connected diagram, not a loose row of separate icons. Between
stage 1 and 2, between 2 and 3, and between 3 and 4, draw one THICK arrow
connecting the LAST node of one stage to the FIRST node of the next, so the
whole thing reads as one continuous pipeline made of four visually distinct
chapters, not four unrelated panels.

STYLE
Flat vector illustration, off-white background (#F7F8FA). Each stage
super-container has a soft 12% opacity fill in its stage colour AND a visible
thin 2px border in the same colour, fully enclosing its internal nodes -- this
border matters here, unlike a plain wash, because these four containers are
meant to read as distinct grouped chapters, each a coherent step. Inside each
container, nodes are small white rounded cards with a 1px grey border, a line
icon, a bold label and a small grey subtitle. Internal arrows are 2px dark
grey with small arrowheads. The stage-to-stage handoff arrows are thicker,
6px, in a slightly darker shade of the colour they are leaving, so they read
as more important than the internal wiring. All text exactly as given below.
No 3D, no watermark, no real company logos -- write "Ollama" and "NVIDIA NIM"
as plain text only.

TECH TAGS -- IMPORTANT
Under the named nodes listed below, add a tiny monospace tag in a small grey
rounded chip naming the ACTUAL technology, the way a real system diagram does.
These are small (about 60% of the subtitle size) and sit at the bottom edge of
their card. Use exactly these strings:
    CAPTURE          -> "Win32 · UI Automation"
    PANEL OPENS      -> "Tauri v2"
    MEMORY STORE     -> "SQLite + sqlite-vec"
    RANKER           -> "nomic-embed-text"
    LOCAL -- Ollama  -> "qwen2.5"
Do not invent tech tags for any other node.

INPUT COLUMN -- far left, OUTSIDE and to the left of Stage 1, no coloured
container, just two small labelled groups stacked vertically with a thin
bracket joining each group to its arrow:

  Group A, small grey header "WHERE YOU WORK":
    four small file/app icons in a 2x2 grid, labelled exactly
    "PDF", "IDE", "BROWSER", "EMAIL"
    -> one arrow from this group into the "TRIGGER" node in Stage 1,
       labelled "you select something"

  Group B, small grey header "WHERE YOUR CONTEXT COMES FROM":
    three small document icons in a row, labelled exactly
    "ChatGPT export", "Claude export", "Gemini Takeout"
    -> one arrow from this group going into the "MEMORY STORE" node inside
       Stage 2, labelled "imported once, parsed locally"
    This arrow enters Stage 2 from the left and must be visibly SEPARATE from
    the main Stage 1 -> Stage 2 handoff arrow -- it is a different, one-time
    path, so draw it thinner and in grey.

A small "USER" node (person icon) sits just above the INPUT COLUMN, with a
short arrow down into Group A, labelled "selects text, presses a key".

STAGE 1 -- colour BLUE (#4D8DF0), header "1. SUMMON"
  Inside the container, in order, connected by arrows:
    "TRIGGER" -- one card with three small icons together (keyboard, cursor-
       select, camera), subtitle "hotkey · selection · screenshot -- any one
       of the three summons PERCH"
    -> "CAPTURE" -- cursor-select icon, subtitle "UI Automation, or clipboard
       fallback; the host window's handle is saved here"
    -> "PANEL OPENS" -- floating window icon, subtitle "a small popup appears
       beside your work, without taking focus"
    -> "YOUR QUESTION" -- speech-bubble icon, subtitle "typed into the panel,
       alongside whatever was captured"
  "YOUR QUESTION" is the exit point of Stage 1.

STAGE 2 -- colour GREEN (#22A06B), header "2. UNDERSTAND WHAT YOU KNOW"
  Make this container visibly WIDER than the other three -- it holds the most
  components, and its size should say so at a glance. Inside, connected by
  arrows in this order:
    "PRIVACY DECISION" -- shield icon, subtitle "source rules, not content"
    -> "ROUTER" -- signpost icon, subtitle "which memory classes fit this
       question"
    -> "MEMORY STORE" -- DATABASE CYLINDER icon, subtitle "Markdown + SQLite".
       Directly below this node, six small coloured pill tags in a 3x2 grid:
       "IDENTITY", "PROJECT", "ACADEMIC", "CAREER", "HEALTH", "PERSONAL",
       with a tiny padlock glyph on "HEALTH" and "PERSONAL" only.
    -> "RANKER" -- its OWN separate white card with a sort-arrows icon,
       subtitle "orders candidates by relevance to this question". It must be
       a full card of its own, the same size as the others -- do not let its
       label float loose above the next node or merge into it.
    -> "ADMISSION GATE" -- a SEPARATE card, filter-funnel icon, THICKER
       border, small star badge in the corner, subtitle "per-class floor +
       margin". From here
       draw TWO branches: a GREEN arrow labelled "admitted" continuing right
       to the next node, and a RED DASHED arrow labelled "dropped -- with a
       reason" going down to a small crossed-circle icon that stays fully
       INSIDE this container -- it must not leave Stage 2.
    -> "BUDGET PACKER" -- stacked-layers icon, subtitle "context_window(model)
       minus reserves for the response, system prompt and tool schemas"
  BUDGET PACKER receives only the GREEN "admitted" branch, and is the exit
  point of Stage 2.

STAGE 3 -- colour ORANGE (#F0913A), header "3. ANSWER"
  Inside, connected by arrows:
    "MODEL REGISTRY" -- list icon, subtitle "context window per model"
    -> fans out with three short arrows to three route cards stacked in a
       tight column, all the same size: "LOCAL -- Ollama" (chip icon, "free,
       offline, private"), "FREE TIER -- NVIDIA NIM" (cloud icon, "no card,
       100+ models"), "YOUR OWN API KEY" (key icon, "whatever you already
       pay for")
    -> all three route cards connect with short double-headed arrows to
       "TOOL LOOP" (gear icon, subtitle "web / files / docs / python /
       memory -- can call MEMORY STORE again mid-answer")
  Draw one thin, light grey, DASHED arrow from TOOL LOOP back to the MEMORY
  STORE node inside Stage 2, labelled small "can search memory again" -- this
  is the only arrow allowed to reach backward into an earlier stage, and it
  must look visibly different from the main flow so it does not compete with
  it.
  "ANSWER" -- small text-bubble icon, is the exit point of Stage 3.

STAGE 4 -- colour BLUE again (#4D8DF0, same as Stage 1 -- this is the surface
layer closing the loop), header "4. DELIVER"
  Inside, EXACTLY ONE node -- do not duplicate it, do not draw it twice:
    "EDIT IN PLACE" -- pencil-on-document icon, subtitle "Replace / Insert
       after / Copy"
  Draw one long dashed arrow curving from EDIT IN PLACE back to the "PANEL
  OPENS" node in Stage 1, labelled "pastes back into the app you were
  already in" -- route it ABOVE the whole diagram so it does not cross the
  main left-to-right flow.

OUTPUT COLUMN -- far right, OUTSIDE and to the right of Stage 4, no coloured
container, two small artifact cards stacked vertically, each reached by a
short arrow from EDIT IN PLACE:
    a document icon, labelled "YOUR DOCUMENT, EDITED" with small subtitle
       "the selection replaced, in the app you were already in"
    a panel/window icon, labelled "ANSWER + PROVENANCE" with small subtitle
       "which memories were used, which were dropped and why"

CROSS-CUTTING, drawn separately from the main flow, thin grey dashed, no
number badge, small label "private forces local": one arrow from PRIVACY
DECISION in Stage 2 down to MODEL REGISTRY in Stage 3.

BOTTOM ANNOTATION
One single small rounded grey card, fully inside the image with margin on
all sides, not rotated, horizontal text, containing all three lines:
  "Stage 2 is the contribution"
  "Stage 1 is built and running"
  "Stage 3 is what makes it free"

TITLE, top centre, bold: "PERCH — System Architecture"
Subtitle beneath, smaller grey text: "four stages, one continuous request"
```

---

## PROMPT 0a — fix the defects in an existing stage render (edit, don't regenerate)

The first stage render came out largely right, with two real defects and three
omissions. If yours looks like that, paste the image back and use this rather than
regenerating from scratch.

```
Edit this diagram. Keep the four coloured stages, all existing nodes, labels,
colours and arrows exactly as they are, and make only these changes:

1. Stage 4 currently contains TWO identical "EDIT IN PLACE" cards. Delete one
   so exactly one remains.

2. In Stage 2, "RANKER" is currently a loose floating label sitting above the
   Admission Gate card. Give RANKER its own proper white card, the same size
   and style as the others, with a sort-arrows icon and the subtitle "orders
   candidates by relevance to this question", placed between MEMORY STORE and
   ADMISSION GATE and connected to both with arrows.

3. Add a small monospace grey tech tag at the bottom edge of these five cards
   only, reading exactly: CAPTURE -> "Win32 · UI Automation"; PANEL OPENS ->
   "Tauri v2"; MEMORY STORE -> "SQLite + sqlite-vec"; RANKER ->
   "nomic-embed-text"; LOCAL -- Ollama -> "qwen2.5".

4. Add an input column on the far left, outside all coloured stages, with two
   labelled groups: "WHERE YOU WORK" (four small icons: PDF, IDE, BROWSER,
   EMAIL) with an arrow into TRIGGER labelled "you select something"; and
   "WHERE YOUR CONTEXT COMES FROM" (three document icons: "ChatGPT export",
   "Claude export", "Gemini Takeout") with a thinner grey arrow running into
   the MEMORY STORE node inside Stage 2, labelled "imported once, parsed
   locally".

5. Add an output column on the far right, outside all coloured stages, with
   two small cards reached by short arrows from EDIT IN PLACE: "YOUR
   DOCUMENT, EDITED" (document icon, subtitle "the selection replaced, in the
   app you were already in") and "ANSWER + PROVENANCE" (panel icon, subtitle
   "which memories were used, which were dropped and why").

Do not change anything else.
```

---

## PROMPT 0b — if Stage 2 comes out cramped

```
Same diagram, same nodes and edges, but Stage 2 is too cramped. Widen Stage 2
to roughly 40% of the total image width, arrange its six internal nodes
(Privacy Decision, Router, Memory Store, Ranker, Admission Gate, Budget
Packer) in a single flowing S-curve rather than a straight line so they fit
the extra width without leaving dead space, and shrink Stages 1, 3 and 4
proportionally so the total layout still fits 16:9. Keep every label, colour,
icon and edge exactly as before.
```

---

# Alternative structure — four architectural layers instead of four stages

Everything below is the earlier approach: still a connected graph (not sealed boxes), but grouped by
**tier of the codebase** (surface / context / memory / execution) rather than by **stage of a request**.
Keep it around for a slide that specifically needs to show "here is Layer 3, the memory system" in
isolation — the team-split slide (§9.3 of the architecture) maps one-to-one onto these four layers, which
PROMPT 0's stages do not. For the main system-architecture slide, PROMPT 0 above is the better read.

**⚠️ What went wrong the first time this structure was tried, and why PROMPT 1 is rewritten below.** The
first version described four bands and told the model what to put *inside* each one, but never told it
to connect anything *across* them. The result was four sealed boxes with no relationship to each other —
a legend, not an architecture. **The fix is to describe it as a graph: name every node once, then give a
numbered list of directed edges between specific nodes, and forbid enclosing borders around the bands.**
Layers become faint background tints a node sits *on top of*, not containers that stop arrows at their
walls — the same convention AWS/GCP/Azure reference architecture diagrams use, which is almost certainly
what the other groups' diagrams actually were.

---

## ★ PROMPT 1 — the main system architecture (component graph, not a legend)

```
Create a professional software architecture diagram for a desktop AI application
called PERCH. Widescreen 16:9, high resolution, suitable for a university project
review slide.

THIS MUST BE A CONNECTED GRAPH, NOT A SET OF GROUPED BOXES. Every node listed below
is drawn ONCE as a small icon-topped card. Every edge listed below is drawn as a
visible arrow going from one specific named node to another specific named node,
often crossing from one colour zone into a different one. Do not draw any solid
rectangle that encloses a whole group of nodes and stops the arrows at its border
-- that produces four disconnected panels, which is the WRONG result. Instead use
the AWS/GCP/Azure reference-architecture convention: four wide, softly rounded,
low-opacity colour washes laid on the background as horizontal LANES (no visible
border, ~15% opacity fill only, so they read as tinted zones a node sits on top
of), with nodes and arrows drawn on top and free to cross between lanes.

STYLE
Flat vector illustration, clean and uncluttered, soft off-white background
(#F7F8FA). Each node is a small white rounded card with a thin 1.5px border in its
lane's colour, a simple line icon at the top, a bold label, and a smaller grey
subtitle line. Arrows are crisp, 2px, dark grey (#4A4E58), with a small filled
arrowhead, each labelled along its length with a short lowercase caption in a
tiny grey font. All text must be spelled EXACTLY as given below. No 3D, no
watermark, no photorealism, no fake logos of real companies -- write "Ollama" and
"NVIDIA NIM" as plain text only.

FOUR LANES, top to bottom, each a translucent colour wash with a small coloured
tab on the far left edge naming it:
  LANE 1  BLUE wash (#4D8DF0 at 15%)    tab text "L1 SURFACE"
  LANE 2  PURPLE wash (#8B5CF6 at 15%)  tab text "L2 CONTEXT"
  LANE 3  GREEN wash (#22A06B at 15%)   tab text "L3 MEMORY"
  LANE 4  ORANGE wash (#F0913A at 15%)  tab text "L4 EXECUTION"

NODES (name, lane, icon, subtitle) -- draw every one of these exactly once:

  N1  "USER"                lane 0 (no wash, plain white, top-left corner)
                             person icon, subtitle "selects text in any app"
  N2  "HOTKEY"               LANE 1, keyboard icon, subtitle "Ctrl+Alt+Space"
  N3  "CAPTURE"               LANE 1, cursor-select icon, subtitle "UI Automation / clipboard"
  N4  "HOST WINDOW"          LANE 1, small window-frame icon, subtitle "HWND saved here"
  N5  "PANEL"                LANE 1, floating-card icon, subtitle "appears beside your work"
  N6  "PRIVACY DECISION"     LANE 2, shield icon, subtitle "source rules, not content"
  N7  "ROUTER"               LANE 2, signpost icon, subtitle "which classes are eligible"
  N8  "MEMORY STORE"         LANE 3, DATABASE CYLINDER icon, subtitle "Markdown + SQLite"
  N9  "RANKER"               LANE 3, sort-arrows icon, subtitle "orders candidates"
  N10 "ADMISSION GATE"       LANE 3, filter-funnel icon, thicker border, small star
                             badge in the corner, subtitle "per-class floor + margin"
  N11 "BUDGET PACKER"        LANE 2, stacked-layers icon, subtitle "context_window(model) minus reserves"
  N12 "MODEL REGISTRY"       LANE 4, list icon, subtitle "context window per model"
  N13a "LOCAL — Ollama"      LANE 4, chip icon, subtitle "free, offline, private"
  N13b "FREE TIER — NVIDIA NIM"  LANE 4, cloud icon, subtitle "no card, 100+ models"
  N13c "YOUR OWN API KEY"    LANE 4, key icon, subtitle "whatever you already pay for"
  N14 "TOOL LOOP"            LANE 4, gear icon, subtitle "web / files / docs / python / memory"
  N15 "EDIT IN PLACE"        LANE 1, pencil-on-document icon, subtitle "Replace / Insert / Copy"

  Below N8, draw six small coloured pill tags in a 3x2 grid, touching the bottom
  edge of the MEMORY STORE card: "IDENTITY", "PROJECT", "ACADEMIC", "CAREER",
  "HEALTH", "PERSONAL". Put a tiny padlock glyph on "HEALTH" and "PERSONAL" only.

  Stack N13a, N13b and N13c as three small cards in a tight vertical column
  directly to the right of N12, all three the same size, all three at the same
  horizontal position.

EDGES -- draw every one of these as a numbered arrow, using the number as a small
circled label at the midpoint of the arrow:

  1.  N1 -> N2          "press"
  2.  N2 -> N3           "fires"
  3.  N3 -> N4           "snapshot HWND"          (short dashed arrow)
  4.  N3 -> N5           "selection + provenance"
  5.  N5 -> N6           "question"
  6.  N6 -> N7           "cleared"
  7.  N7 -> N8           "eligible classes"
  8.  N8 -> N9           "candidates"
  9.  N9 -> N10          "ranked"
  10. N10 -> N11         GREEN arrow, "admitted"
  11. N10 -> a small red crossed-circle icon floating just below N10, RED DASHED
      arrow, "dropped — with a reason"
  12. N11 -> N12         "assembled prompt"
  13. N12 -> N13a, N12 -> N13b, N12 -> N13c   three short arrows fanning out from
      N12's right edge to each of the three stacked route cards, single label
      "route" placed once next to N12, not repeated three times
  14. N13a <-> N14, N13b <-> N14, N13c <-> N14   three short double-headed arrows,
      each route card connects directly to N14 which sits just to its right;
      one shared label "tool call / result" placed once, centred among the three

  15. *** THIS IS THE EDGE THAT MUST NOT BE LOST ***
      N14 -> N15    a SINGLE long, clean, mostly-straight arrow running up the
      FAR RIGHT OUTER EDGE of the entire image, outside and to the right of all
      four lanes and the side annotation -- starting at N14 (bottom right,
      LANE 4) and ending at N15 (top right, LANE 1). It must be visibly
      unbroken and must NOT terminate early at N11, N12, or any other node it
      passes on the way up. Give it its own dedicated vertical channel of
      empty space so it cannot be confused with any other arrow. Label it once
      at the midpoint: a small circled "15" and the word "answer".

  16. N15 -> N4           "paste back via saved HWND"      (curves back left,
      long dashed arrow, crossing back into LANE 1 -- this is the loop that closes
      the diagram, draw it clearly, do not let it overlap N1-N3 or edge 15)
  17. N6 -> N12          THIN DASHED arrow crossing three lanes downward, small
      label "private forces local" -- this shows privacy constraining execution
      directly, independent of the main numbered flow, draw it visually distinct
      (thin, grey, no number badge) from edges 1-16 so it doesn't look like part
      of the main sequence

SIDE ANNOTATION
Reserve a dedicated empty vertical channel on the far right of the image, wide
enough for the edge-15 arrow (see above) AND, further right of that arrow, a
SINGLE small rounded grey card containing all three lines of text stacked
inside it, horizontal (not rotated), left-aligned, small but fully legible:
  "L2 + L3 are the contribution"
  "L1 is built and running"
  "L4 is what makes it free"
This must be ONE card, fully inside the image bounds with margin on all sides,
never split into separate floating fragments and never rotated 90 degrees.

TITLE, top centre, bold: "PERCH — System Architecture"
Subtitle beneath it, smaller grey text: "one request, from keystroke to edit,
crossing all four layers"
```

---

## PROMPT 1b — if the graph still comes out too tangled

```
Same diagram, same nodes and edges as before, but simplify the ROUTING of the
arrows: use only horizontal and vertical segments with rounded corners (no
diagonal lines), route each arrow along the shortest orthogonal path, and
increase the spacing between nodes in the same lane by 25% so no two arrows
overlap. Keep every node, every label and every edge number exactly as before.
```

---

## PROMPT 1c — targeted fix for THIS render (edit, don't regenerate)

If you already have a render that has the right lane structure and most edges
correct but suffers the specific failures below, this is cheaper and more
reliable than starting over: paste the existing image back in and give Gemini
this as an edit instruction.

```
Edit this diagram. Keep every node, label, colour and edge exactly as they
are, except for these three fixes:

1. The arrow for edge 15 ("answer") currently stops short at the BUDGET
   PACKER node instead of reaching EDIT IN PLACE. Redraw it as a single
   continuous, mostly-straight arrow running up the far right OUTER edge of
   the whole image -- outside all four coloured lanes -- starting at TOOL
   LOOP and ending at EDIT IN PLACE. It must not touch or terminate at any
   node along the way. Keep its "15 answer" label at the midpoint.

2. Add two more small route cards next to the existing "LOCAL — Ollama" card,
   same size, stacked in a tight vertical column at the same horizontal
   position: one labelled "FREE TIER — NVIDIA NIM" with a cloud icon and
   subtitle "no card, 100+ models", and one labelled "YOUR OWN API KEY" with
   a key icon and subtitle "whatever you already pay for". Connect MODEL
   REGISTRY to all three with short fanning arrows, and connect TOOL LOOP to
   all three with short double-headed arrows, the same style as the existing
   connection to "LOCAL — Ollama".

3. The grey side-annotation text is currently split into separate rotated
   fragments and partially cut off at the top and bottom edges of the image.
   Replace it with ONE single rounded grey card, positioned fully inside the
   image with margin on all sides, containing all three lines horizontally
   (not rotated), left-aligned, in a legible size:
     "L2 + L3 are the contribution"
     "L1 is built and running"
     "L4 is what makes it free"

Do not change anything else -- same nodes, same colours, same other arrows,
same title.
```

---

## PROMPT 2 — the request path *(the second-best slide to have)*

Use this if you want one diagram that tells the whole story as a journey rather than as layers.

```
Create a clean horizontal flow diagram, 16:9, flat vector style, off-white
background, for a desktop AI assistant called PERCH. Show one request travelling
left to right through nine stages. Each stage is a rounded box with a small line
icon, connected by thin arrows. Colour-code the boxes by which layer they belong
to: BLUE (#4D8DF0) for surface, PURPLE (#8B5CF6) for context, GREEN (#22A06B) for
memory, ORANGE (#F0913A) for execution.

The nine stages, labelled exactly, in this order:

1. BLUE   "USER SELECTS TEXT"      subtext "in any Windows application"
2. BLUE   "HOTKEY"                 subtext "Ctrl+Alt+Space"
3. BLUE   "CAPTURE"                subtext "UI Automation, clipboard fallback"
4. PURPLE "PRIVACY DECISION"       subtext "from the source, not the content"
5. PURPLE "CLASS ROUTING"          subtext "which memory classes are eligible"
6. GREEN  "RANK"                   subtext "order the candidates"
7. GREEN  "ADMIT"                  subtext "per-class floor, or nothing at all"
8. ORANGE "MODEL + TOOLS"          subtext "local, free tier, or your key"
9. BLUE   "EDIT IN PLACE"          subtext "back into the document you were in"

Below stage 6 and 7, draw a small green cylinder database icon labelled
"YOUR MEMORY" with an arrow pointing up into stage 6.

From stage 7, draw a short red dashed arrow pointing downward to a small box
labelled "ABSTAIN" with subtext "nothing relevant stored — and it says so".

At the top, bold title: "PERCH — One Request, End to End"
```

---

## PROMPT 3 — the contribution, on its own

Use this on the ranker/admission slide. It is the single idea the panel most needs to *see*.

```
Create a simple, striking explanatory diagram, 16:9, flat vector, off-white
background, contrasting two approaches side by side. Clean sans-serif text,
spelled exactly as given.

Title at the top, bold: "Ranking is relative. Injection must be absolute."

LEFT HALF, under a red heading "WITHOUT A GATE":
Show a magnifying glass over a small green database cylinder labelled "MEMORY".
An arrow leads to a vertical list of three ranked result cards:
  1. "College: PES Modern, B.E. Computer Engineering"   with a small tag "ACADEMIC"
  2. "Project: PERCH desktop agent"                     with a small tag "PROJECT"
  3. "Targeting backend roles"                          with a small tag "CAREER"
An arrow from the list leads to a speech bubble containing:
  "You asked about your MEDICATION."
  "Here are your COLLEGE details."
Put a large red X badge on the speech bubble.

RIGHT HALF, under a green heading "WITH A PER-CLASS FLOOR":
Show the same magnifying glass and database. Show the same three result cards,
but each card is greyed out and struck through, with a small red label to its
right reading exactly "below class floor".
Draw a horizontal dashed red line across the cards labelled "FLOOR".
An arrow leads to a speech bubble containing:
  "I have nothing stored about this."
  "Answering from general knowledge."
Put a large green tick badge on the speech bubble.

At the bottom, a single centred caption in grey:
"A class whose best candidate falls below its floor contributes nothing — not the
best of a bad lot."
```

---

## Follow-up edits — what usually needs fixing

Paste these one at a time after the first image comes back.

| Problem | What to say |
|---|---|
| Any text is misspelled | *"Keep the exact same layout and colours, but fix the text: it must read exactly `<the correct label>`."* |
| Too busy | *"Same diagram, but remove all decorative elements, increase the white space between bands by 40%, and make the connector arrows thinner."* |
| Colours washed out | *"Increase the saturation of the four band colours and make the coloured left-edge strips wider so the four layers separate at a glance."* |
| The database looks wrong | *"Replace the storage icon with a classic three-disc cylinder database symbol in green."* |
| Icons are inconsistent | *"Redraw all icons in a single consistent style: thin two-pixel line icons, no fills, same visual weight."* |
| Nothing stands out | *"Emphasise the ADMISSION GATE box: thicker border, a soft coloured glow, and a small star badge. Everything else stays as it is."* |
| Wrong shape for a slide | *"Recompose to a strict 16:9 with a 5% margin on all sides and nothing cropped."* |
| **Came back as sealed boxes again, no cross-lane arrows** | *"Keep the same nodes, but remove the solid rectangle border around each lane entirely — replace it with only a faint colour wash and no outline — and make sure every numbered arrow from the edge list is visibly drawn crossing from one lane into the next. The lanes must not look like separate containers."* |

---

## Before it goes on a slide

- [ ] **Read every word in the image.** Image models invent plausible technical text; the reviewer will read it.
- [ ] **The six class names are exactly** Identity · Project · Academic · Career · Health · Personal.
- [ ] **Health and Personal carry the padlock**, nothing else does.
- [ ] **The dropped/abstain path is visible.** It is the contribution; a diagram that only shows the happy path shows a normal RAG pipeline.
- [ ] **No real company logos.** Write "Ollama" and "NVIDIA NIM" as text, never as marks.
- [ ] **It matches the deck.** Same four layers, same order, same colours as slide 13.
- [ ] **Trace edge 15 with your finger from Tool Loop to Edit In Place.** If it stops early at any other box, that box is quietly claiming to be the last step — say so and use PROMPT 1c.
- [ ] **Three route cards are visible under Model Registry** — local, free tier, and your own key. One route alone undersells the actual pitch (model choice is free for us, expensive for a $50M-funded competitor to offer).
- [ ] **The side annotation is one legible card, not split or rotated.**
- [ ] **Count the arrows, not the boxes.** There should be visible connectors crossing between colour zones — surface into context, context into memory, memory back into context, execution back into surface (edge 16, the paste-back loop). If you can cover any single lane with your hand and the diagram still makes sense as "four separate lists," the connections did not render — ask for the PROMPT 1b orthogonal-routing follow-up, or the fix in the table above.
