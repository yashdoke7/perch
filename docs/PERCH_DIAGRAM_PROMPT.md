# PERCH — architecture diagram prompt (Gemini 3 Pro Image / "Nano Banana Pro")

**Why a prompt and not Mermaid.** The panel responded better to the coloured, icon-led architecture
diagrams other groups produced than to monochrome Mermaid. Nano Banana Pro renders legible in-image
text, which is the part most image models get wrong — so the prompt below **spells out every label
verbatim**, because anything you leave to the model comes back as plausible-looking gibberish.

**How to use it.** Paste PROMPT 1 into Gemini with image generation. Then use the follow-ups to fix
whatever came out wrong — it is much better at editing an existing image than at getting a dense
diagram right first time. Ask for **16:9** and the highest resolution offered.

---

## ★ PROMPT 1 — the main system architecture

```
Create a professional software architecture diagram for a desktop AI application
called PERCH. Widescreen 16:9, high resolution, suitable for a university project
review slide.

STYLE
Modern technical architecture diagram, flat vector illustration, clean and
uncluttered. Soft off-white background (#F7F8FA). Rounded rectangles with subtle
drop shadows. Crisp thin connector arrows in dark grey. All text in a clean sans
serif, dark charcoal (#1F2430), and every label must be spelled EXACTLY as written
below. Generous white space. No photorealism, no 3D, no gradients on text, no
watermark, no fake logos of real companies.

LAYOUT
Four horizontal bands stacked top to bottom, each band a wide rounded container
with a coloured left edge strip and its name written vertically or in the top-left
corner. A vertical flow arrow runs down the left side of all four bands.

BAND 1 — top — colour BLUE (#4D8DF0), title "LAYER 1 — SURFACE"
Inside, four boxes in a row, each with a simple line icon above its label:
  - keyboard icon, label "TRIGGER" and small subtext "hotkey / selection / screenshot"
  - cursor-with-text-selection icon, label "CAPTURE" and subtext "UI Automation, clipboard fallback"
  - floating side-panel icon, label "PANEL" and subtext "beside your work, never over it"
  - document-with-pencil icon, label "EDIT IN PLACE" and subtext "Replace / Insert / Copy"

BAND 2 — colour PURPLE (#8B5CF6), title "LAYER 2 — CONTEXT"
Inside, three boxes in a row:
  - shield icon, label "PRIVACY" and subtext "source rules, not content"
  - signpost icon, label "ROUTER" and subtext "which memory classes are eligible"
  - stacked-layers icon, label "BUDGET PACKER" and subtext "context_window(model) - reserves"

BAND 3 — colour GREEN (#22A06B), title "LAYER 3 — MEMORY"
On the left of this band, draw a CYLINDER DATABASE ICON in green, labelled
"MARKDOWN + SQLITE" with small subtext "the files are the truth".
To its right, six small coloured pill-shaped tags in two rows of three, reading
exactly: "IDENTITY", "PROJECT", "ACADEMIC", "CAREER", "HEALTH", "PERSONAL".
Draw a small orange padlock icon on the "HEALTH" and "PERSONAL" pills only.
To the right of the pills, two boxes connected by a short arrow:
  - label "RANKER" with subtext "orders candidates"
  - label "ADMISSION GATE" with subtext "per-class floor + margin"
Draw the ADMISSION GATE box with a slightly thicker border and a small star or
badge in its corner to mark it as the key component.
From the ADMISSION GATE, draw TWO outgoing arrows:
  a green arrow labelled "ADMITTED" going right,
  and a red dashed arrow labelled "DROPPED — with a reason" curving away downward
  into a small crossed-circle symbol.

BAND 4 — bottom — colour ORANGE (#F0913A), title "LAYER 4 — EXECUTION"
Inside, on the left a box labelled "MODEL REGISTRY".
To its right, three parallel route boxes stacked vertically:
  - a small computer-chip icon, label "LOCAL — Ollama", subtext "free, offline, private"
  - a small cloud icon, label "FREE TIER — NVIDIA NIM"
  - a small key icon, label "YOUR OWN API KEY"
To the right of those, a box labelled "TOOL LOOP" with six tiny icons inside and
the caption "web · files · documents · OCR · python · memory".

SIDE ANNOTATIONS
On the far right of the image, a narrow vertical callout panel in light grey
containing three short lines of text exactly:
  "L2 + L3 are the contribution"
  "L1 is built and running"
  "L4 is what makes it free"

TITLE
At the very top, centred, in bold: "PERCH — System Architecture"
Directly under it in smaller grey text: "A personal AI agent that lives where your
desktop lives"
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
2. BLUE   "HOTKEY"                 subtext "Ctrl+Shift+Space"
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

---

## Before it goes on a slide

- [ ] **Read every word in the image.** Image models invent plausible technical text; the reviewer will read it.
- [ ] **The six class names are exactly** Identity · Project · Academic · Career · Health · Personal.
- [ ] **Health and Personal carry the padlock**, nothing else does.
- [ ] **The dropped/abstain path is visible.** It is the contribution; a diagram that only shows the happy path shows a normal RAG pipeline.
- [ ] **No real company logos.** Write "Ollama" and "NVIDIA NIM" as text, never as marks.
- [ ] **It matches the deck.** Same four layers, same order, same colours as slide 13.
