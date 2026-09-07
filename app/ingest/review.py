"""Human review of extracted proposals (architecture §3.4, rule 2).

    "On import, extraction is gated. The extractor proposes items; the user
     reviews and accepts. Rejected items are not stored."

This module is the only thing standing between a model's opinion about you and
your permanent memory, so it is deliberately dull: it shows one item at a time,
in full, and stores nothing until a person types y.

Three properties that are not negotiable:

  * NOTHING IS WRITTEN UNTIL REVIEW ENDS. Quitting half-way stores the items
    already accepted and nothing else -- but the write happens in one pass at
    the end, so an interrupted review cannot leave memory half-updated.
  * THE DEFAULT IS NO. A bare Enter rejects. Import runs over hundreds of
    items and the failure mode of a y-default is a memory full of things
    nobody read.
  * MERGES ARE REPORTED. store.add() may update an existing item instead of
    creating one (§3.4 rule 3). The user is told which happened, because
    "23 stored" and "18 created, 5 merged" mean different things.

I/O is injected rather than hard-coded to input()/print() so the whole triage
loop is testable headlessly, which is the reason it is a plain function and
not a class holding a terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..memory.store import MemoryStore
from .extract import Proposal

HELP = """
  y  accept        n  reject (default)     e  edit the title
  a  accept all remaining                  d  reject all remaining
  ?  show this help                        q  finish review now
"""


@dataclass
class Summary:
    accepted: int = 0
    rejected: int = 0
    created: list[str] = field(default_factory=list)
    merged: list[str] = field(default_factory=list)
    quit_early: bool = False

    def lines(self) -> list[str]:
        out = [f"reviewed: {self.accepted} accepted, {self.rejected} rejected"]
        if self.quit_early:
            out.append("  (review ended early; unreviewed items were not stored)")
        if self.created:
            out.append(f"  created {len(self.created)} new items")
        if self.merged:
            out.append(f"  merged  {len(self.merged)} into items you already had")
            for title in self.merged[:5]:
                out.append(f"     ~ {title}")
        if not self.created and not self.merged:
            out.append("  nothing was written to memory")
        return out


def render(proposal: Proposal, n: int, total: int) -> str:
    """One proposal, in full. Never truncated -- you cannot approve what you
    have not been shown, and this is the only point at which anyone looks."""
    item = proposal.item
    # ASCII, deliberately. Box-drawing (U+2500) is not in cp1252, which is
    # still the default console encoding on Windows -- the target platform --
    # so printing it raised UnicodeEncodeError and took the whole import down
    # at the moment it had proposals to show. main() now forces UTF-8 on
    # stdout as well, but a review header is not worth a second chance to
    # break: this is the screen a user has to read to approve their memory.
    head = f"-- {n}/{total} -- [{item.cls}] " + "-" * 34
    body = "\n".join(f"    {ln}" for ln in item.body.splitlines())
    parts = [
        head,
        f"  {item.title}",
        "",
        body,
        "",
        f"  tags     {', '.join(item.tags) or '(none)'}",
    ]
    if item.entities:
        parts.append(f"  entities {', '.join(item.entities)}")
    parts.append(f"  source   {item.source_platform or 'unknown'}"
                 f"{' — ' + proposal.session_title if proposal.session_title else ''}")
    parts.append(f"  extractor confidence {proposal.confidence:.2f}")
    for w in proposal.warnings:
        parts.append(f"  !! {w}")
    return "\n".join(parts)


def uncalibrated(proposals: list[Proposal]) -> bool:
    """Did the extractor give every item the same confidence?

    Measured with qwen2.5:3b on a real ChatGPT export: it emitted
    `confidence: 1` for all four items it produced. It is not estimating
    anything -- it is filling in the field because the contract asks for it.

    That matters because the number is shown to the reviewer, and a number
    shown to a human is read as information. Worse, the "extractor was
    unsure" warning keys off it, so a model that always says 1 silently
    disables the one automatic signal the review screen had. Better to say
    the number is meaningless than to display it as though it were not.

    A larger model may calibrate; this is checked per batch rather than
    assumed either way.
    """
    if len(proposals) < 2:
        return False
    return len({round(p.confidence, 3) for p in proposals}) == 1


def review(proposals: list[Proposal], store: MemoryStore,
           ask=input, out=print) -> Summary:
    """Triage every proposal, then write the accepted ones in one pass."""
    summary = Summary()
    if not proposals:
        out("nothing was extracted, so there is nothing to review")
        return summary

    out(f"\n{len(proposals)} proposed items. Enter rejects; ? for help.")
    if uncalibrated(proposals):
        out(f"\n  !! Every item came back at confidence "
            f"{proposals[0].confidence:.2f}. The extractor is not calibrating,")
        out("     it is filling in a required field -- so ignore that number here,")
        out("     and read each body on its own merits.")
    out("\n  Extracted text is a model's PARAPHRASE of your conversation, not a")
    out("  quote from it. Small models restate confidently and get details wrong,")
    out("  including inventing outcomes that were never stated. That is what this")
    out("  screen is for.")
    out(HELP)

    bulk: str | None = None          # set by 'a' or 'd' to skip the prompt
    for i, proposal in enumerate(proposals, 1):
        if bulk is None:
            out("\n" + render(proposal, i, len(proposals)))
            while True:
                try:
                    answer = (ask("  keep? [y/N/e/a/d/q/?] ") or "n").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    out("\n(input closed — ending review)")
                    answer = "q"
                if answer == "?":
                    out(HELP)
                    continue
                break
        else:
            answer = bulk

        if answer == "q":
            summary.quit_early = True
            break
        if answer == "a":
            bulk = answer
            answer = "y"
        elif answer == "d":
            bulk = answer
            answer = "n"
        elif answer == "e":
            try:
                new_title = (ask(f"  new title [{proposal.item.title}]: ") or "").strip()
            except (EOFError, KeyboardInterrupt):
                new_title = ""
            if new_title:
                proposal.item.title = new_title[:120]
            answer = "y"

        if answer == "y":
            proposal.accepted = True
            summary.accepted += 1
        else:
            summary.rejected += 1

    # --- the single write pass ------------------------------------------
    # Deliberately after the loop, not inside it. Storing as we go would mean
    # a Ctrl+C in the middle leaves memory in a state the user never saw a
    # summary of.
    for proposal in proposals:
        if not proposal.accepted:
            continue
        stored, how = store.add(proposal.item)
        (summary.merged if how == "merged" else summary.created).append(stored.title)

    return summary
