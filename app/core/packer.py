"""The budget packer (architecture §4.5) -- Contribution 1.

    budget = context_window(model) - response - system - tool schemas

Fill order is a strict priority, and memory gets what is left:

    1. system + identity      small, always
    2. the selection          always -- it is why the user summoned us
    3. recent conversation    oldest turns truncated first
    4. admitted memory        in ranker order, into whatever remains
    5. tool results           claimed from the same allowance when a tool runs

Two rules that matter more than they look:

  * ITEMS ENTER WHOLE OR NOT AT ALL. Half a project decision is worse than
    none -- it reads as a confident, incomplete fact.

  * MEMORY AND TOOLS COMPETE FOR ONE BUDGET. The 2026 externalization survey
    calls this "a harness-level coordination problem" and leaves it open. It
    is why swapping Qwen3 4B for a frontier API changes nothing but a number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .. import config
from ..memory.schema import Scored


@dataclass
class Packed:
    system: str
    prompt: str
    included: list[Scored] = field(default_factory=list)
    evicted: list[Scored] = field(default_factory=list)
    budget: int = 0
    used: int = 0

    @property
    def headroom(self) -> int:
        return max(0, self.budget - self.used)

    def summary(self) -> str:
        return (f"budget {self.budget} tok | used ~{self.used} | "
                f"{len(self.included)} items in, {len(self.evicted)} evicted")


BASE_SYSTEM = (
    "You are PERCH, the user's own assistant. You run on their desktop and you "
    "know them. Answer directly and concisely.\n"
    "If the user asks you to rewrite the selected text, reply with ONLY the "
    "rewritten text and nothing else.\n"
    "Use the personal context below only where it is genuinely relevant. If it "
    "is not relevant, ignore it -- do not mention the user's background just "
    "because you were given it."
)

ABSTAIN_NOTE = (
    "\n\nNOTE: nothing in the user's stored memory was relevant to this "
    "request. Answer from general knowledge. Do not invent personal details, "
    "and if the question clearly needed personal context, say plainly that you "
    "have none stored for it."
)


def _tokens(text: str) -> int:
    return int(len(text) / config.CHARS_PER_TOKEN) + 1


def pack(question: str, selection: str, admitted: list[Scored],
         context_window: int, history: list[tuple[str, str]] | None = None,
         abstained: bool = False, tools_declared: bool = False) -> Packed:

    reserves = config.RESERVE_RESPONSE + config.RESERVE_SYSTEM
    if tools_declared:
        reserves += config.RESERVE_TOOLS
    budget = max(512, context_window - reserves)

    used = 0
    system = BASE_SYSTEM + (ABSTAIN_NOTE if abstained else "")
    used += _tokens(system)

    # (2) the selection -- always, truncated from the middle if it is enormous,
    # because the head and tail of a selection carry the most meaning.
    sel_block = ""
    if selection.strip():
        sel = selection.strip()
        cap = int(budget * 0.45)
        if _tokens(sel) > cap:
            keep = int(cap * config.CHARS_PER_TOKEN / 2)
            sel = sel[:keep] + "\n[...truncated...]\n" + sel[-keep:]
        sel_block = f"SELECTED TEXT (from the user's screen):\n{sel}\n\n"
        used += _tokens(sel_block)

    # (3) conversation, oldest first out
    hist_block = ""
    for role, text in reversed(history or []):
        turn = f"{role.upper()}: {text}\n"
        if used + _tokens(turn) > budget * 0.75:
            break
        hist_block = turn + hist_block
        used += _tokens(turn)
    if hist_block:
        hist_block = f"RECENT CONVERSATION:\n{hist_block}\n"

    # (4) memory -- whole items only
    included: list[Scored] = []
    evicted: list[Scored] = []
    mem_lines: list[str] = []
    question_cost = _tokens(f"QUESTION:\n{question}\n\nANSWER:")

    for scored in admitted:
        block = scored.item.rendered()
        cost = _tokens(block) + 2
        if used + cost + question_cost <= budget:
            mem_lines.append(block)
            included.append(scored)
            used += cost
        else:
            scored.admitted = False
            scored.reason = "evicted: no budget left"
            evicted.append(scored)

    mem_block = ""
    if mem_lines:
        mem_block = "WHAT YOU KNOW ABOUT THIS USER:\n" + "\n\n".join(mem_lines) + "\n\n"

    prompt = f"{mem_block}{sel_block}{hist_block}QUESTION:\n{question}\n\nANSWER:"
    used += question_cost

    return Packed(system=system, prompt=prompt, included=included,
                  evicted=evicted, budget=budget, used=used)
