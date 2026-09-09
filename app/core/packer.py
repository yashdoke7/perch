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
from ..memory import classes
from ..memory.schema import Scored


@dataclass
class Packed:
    system: str
    prompt: str
    included: list[Scored] = field(default_factory=list)
    evicted: list[Scored] = field(default_factory=list)
    budget: int = 0
    used: int = 0

    # The pieces the prompt was assembled from, kept so it can be re-rendered
    # after an eviction. Without these, "the packer may evict low-ranked
    # memory to make room" is not implementable -- you cannot un-bake a string.
    question: str = ""
    sel_block: str = ""
    hist_block: str = ""

    @property
    def headroom(self) -> int:
        return max(0, self.budget - self.used)

    def summary(self) -> str:
        note = f", {len(self.evicted)} evicted" if self.evicted else ""
        return (f"budget {self.budget} tok | used ~{self.used} | "
                f"{len(self.included)} items in{note}")

    # ------------------------------------------------------ the live ledger

    def _render(self) -> str:
        mem_block = ""
        if self.included:
            mem_block = ("WHAT YOU KNOW ABOUT THIS USER:\n"
                         + "\n\n".join(s.item.rendered() for s in self.included) + "\n\n")
        return (f"{mem_block}{self.sel_block}{self.hist_block}"
                f"QUESTION:\n{self.question}\n\nANSWER:")

    def charge(self, text: str) -> None:
        """Account for something added to the conversation after packing.

        Tool results and the model's own intermediate turns occupy the same
        context window as memory does. Not charging them is how a budget that
        looks respected on paper overflows in practice.
        """
        self.used += _tokens(text)

    def make_room(self, need: int) -> list[Scored]:
        """Evict the lowest-ranked memory until `need` tokens are free.

        ★ This is the concrete form of Contribution 1. The claim is not that
        memory has a budget -- every system has that -- it is that memory and
        tool results are charged against ONE allowance, so a tool call that
        returns something big costs you your weakest memory rather than
        silently costing you the end of your own prompt.

        Eviction runs from the bottom of the ranker's order, which is why
        included[] is kept sorted: the item we can most afford to lose is the
        one the ranker already said was least useful.

        IDENTITY IS NEVER EVICTED. That is not a special case bolted on -- it
        is the same decision §4.5's fill order already makes when it puts
        "system + Identity" first and calls it "small, always". Identity is
        what makes an answer sound like you; a web search result that costs
        you your own voice is a bad trade at any size, and identity items are
        small enough that protecting them frees almost nothing anyway. When
        only identity is left, the caller truncates the tool result instead.
        """
        thrown: list[Scored] = []
        freed = 0
        # Walk from the back, skipping protected items rather than stopping at
        # the first one -- an identity item mid-list must not shield the
        # lower-ranked project items behind it.
        i = len(self.included) - 1
        while freed < need and i >= 0:
            if classes.is_protected_from_eviction(self.included[i].item.cls):
                i -= 1
                continue
            victim = self.included.pop(i)
            victim.admitted = False
            victim.reason = "evicted: a tool result needed the budget"
            self.evicted.append(victim)
            thrown.append(victim)
            freed += _tokens(victim.item.rendered()) + 2
            i -= 1
        if thrown:
            self.used -= freed
            self.prompt = self._render()
        return thrown


# Open-weight chat models (Qwen, Llama, etc.) ship with a baked-in identity
# in their own training -- ask one "what company made you" with no system
# prompt override and it will answer honestly as the base model ("I am Qwen,
# developed by Alibaba Cloud"), because nothing has told it otherwise. That
# is correct default behaviour for the base model and wrong for a product
# built on top of it: PERCH is meant to present as one coherent assistant
# regardless of which model is answering underneath, local or cloud, so the
# system prompt has to say so explicitly rather than leave it to whatever
# the underlying model happens to default to.
BASE_SYSTEM = (
    "You are PERCH, the user's own personal AI assistant, running on their "
    "desktop. You run on their desktop and you know them. Answer directly "
    "and concisely.\n"
    "If asked who or what you are, what model, company or vendor is behind "
    "you, or any similar identity question, answer only that you are PERCH, "
    "the user's personal AI agent that runs locally on their own machine. "
    "Do not name, guess at, or confirm any underlying model, provider or "
    "company, even if you would otherwise identify yourself that way -- the "
    "user chose which model answers this; it is not part of the answer.\n"
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


IMAGE_ATTACHED = (
    "\n\nA screenshot the user captured is attached to this message. Read it "
    "and answer about what it shows.")

# Said in the prompt, not only in the panel, because the model is the one that
# would otherwise invent a description of a picture it never received.
IMAGE_UNREADABLE = (
    "\n\nNOTE: the user captured a screenshot, but the model answering this "
    "request cannot read images, so it was NOT attached. Say plainly that you "
    "could not see it. Do not guess at its contents.")


def pack(question: str, selection: str, admitted: list[Scored],
         context_window: int, history: list[tuple[str, str]] | None = None,
         abstained: bool = False, tools_declared: bool = False,
         image_attached: bool = False, image_unreadable: bool = False) -> Packed:

    reserves = config.RESERVE_RESPONSE + config.RESERVE_SYSTEM
    if tools_declared:
        reserves += config.RESERVE_TOOLS
    budget = max(512, context_window - reserves)

    used = 0
    system = BASE_SYSTEM + (ABSTAIN_NOTE if abstained else "")
    if image_attached:
        system += IMAGE_ATTACHED
    elif image_unreadable:
        system += IMAGE_UNREADABLE
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
    question_cost = _tokens(f"QUESTION:\n{question}\n\nANSWER:")

    for scored in admitted:
        cost = _tokens(scored.item.rendered()) + 2
        if used + cost + question_cost <= budget:
            included.append(scored)
            used += cost
        else:
            scored.admitted = False
            scored.reason = "evicted: no budget left"
            evicted.append(scored)

    used += question_cost

    packed = Packed(system=system, prompt="", included=included,
                    evicted=evicted, budget=budget, used=used,
                    question=question, sel_block=sel_block, hist_block=hist_block)
    # Rendered through the same path an eviction uses, so the two can never
    # drift into producing differently-shaped prompts.
    packed.prompt = packed._render()
    return packed
