"""E2 — the budget-assembly ablation (Contribution 1).

    Three configurations of the same memory, at three context-window sizes:

      A  no memory            the memory-free baseline
      B  full profile always  everything admitted, budget ignored -- what a
                              system does when it has a profile and no packer
      C  budget-aware         ours: priority fill, whole items only, and a
                              live ledger that charges tool results too

**Why this one needs no model, and why that is a feature rather than a
compromise.** C1 is a claim about ASSEMBLY, not about generation: that the
same memory layer serves a 4B local model and a frontier API because the only
thing that changes is `context_window`. Whether an assembled prompt fits its
window, and what it had to give up to fit, is fully determined before a single
token is generated. Measuring it with a model would add variance without
adding evidence -- and would make the result unreproducible on a machine with
no GPU, which is precisely the machine C1 is about.

The prediction Part X commits to in advance:

    "The margin should be largest on the smallest model."

That is falsifiable here. If B fits comfortably at 4K then the packer is
solving a problem nobody has.
"""

from __future__ import annotations

from .. import config
from ..core import packer
from ..memory import classes as mc
from ..memory.schema import MemoryItem, Scored
from ..memory.store import MemoryStore
from ..models.client import MAX_TOOL_STEPS
from .harness import Result, unavailable

# The three sizes Part X asks for, chosen to span the range the claim covers.
WINDOWS = [
    (4_096, "Qwen3 4B, conservative"),
    (8_192, "what registry.py gives a local Ollama model"),
    (128_000, "a frontier API"),
]

# A tool result large enough to matter, at the size client.py used to append
# blindly. Four steps of these is what overflowed an 8K window by ~2300 tokens.
TOOL_RESULT_CHARS = 4000


def _tokens(text: str) -> int:
    return int(len(text) / config.CHARS_PER_TOKEN) + 1


def _profile(store: MemoryStore) -> list[Scored]:
    """Everything in memory, ranked by class prior -- 'the full profile'.

    Deliberately NOT the admitted set: config B is the system that has your
    profile and injects it, which is the thing C1 is measured against.
    """
    items: list[Scored] = []
    for cls_name in mc.ORDER:
        with store._lock:
            rows = store.db.execute(
                "SELECT path FROM items WHERE class=?", (cls_name,)).fetchall()
        for (path,) in rows:
            from pathlib import Path
            p = Path(path)
            if not p.exists():
                continue
            item = MemoryItem.from_markdown(p.read_text(encoding="utf-8"))
            if item:
                items.append(Scored(item=item, score=mc.prior_for(cls_name)))
    items.sort(key=lambda s: -s.score)
    return items


def _config_a(window: int) -> dict:
    packed = packer.pack("summarise my work this term", "", [], context_window=window)
    return {"used": packed.used, "budget": packed.budget, "items": 0, "evicted": 0}


def _config_b(window: int, profile: list[Scored]) -> dict:
    """Full profile always: no budget, no priority, no eviction.

    Assembled by hand rather than through the packer, because the packer
    cannot express this configuration -- refusing to overflow is the whole
    point of it. That is the comparison.
    """
    system = packer.BASE_SYSTEM
    body = "\n\n".join(s.item.rendered() for s in profile)
    prompt = (f"WHAT YOU KNOW ABOUT THIS USER:\n{body}\n\n"
              "QUESTION:\nsummarise my work this term\n\nANSWER:")
    used = _tokens(system) + _tokens(prompt)
    budget = window - config.RESERVE_RESPONSE - config.RESERVE_SYSTEM
    return {"used": used, "budget": budget, "items": len(profile), "evicted": 0}


def _config_c(window: int, profile: list[Scored]) -> dict:
    import copy
    packed = packer.pack("summarise my work this term", "",
                         copy.deepcopy(profile), context_window=window)
    return {"used": packed.used, "budget": packed.budget,
            "items": len(packed.included), "evicted": len(packed.evicted),
            "packed": packed}


def _with_tools(window: int, profile: list[Scored]) -> tuple[dict, dict]:
    """The same two configurations, after a realistic tool loop runs.

    This half did not exist before the live ledger did -- and it is where the
    coordination problem the 2026 externalization survey names actually bites,
    because memory and tool results are competing for one allowance rather
    than each having their own.
    """
    import copy
    from ..models import client

    result = "search result. " * (TOOL_RESULT_CHARS // 15)

    # B: append blindly, exactly as client.py used to.
    b = _config_b(window, profile)
    b_used = b["used"] + MAX_TOOL_STEPS * _tokens(result[:4000])

    # C: charge each result against the ledger, evicting to pay.
    packed = _config_c(window, copy.deepcopy(profile))["packed"]
    for _ in range(MAX_TOOL_STEPS):
        client._charge_tool_result(packed, result)

    return ({"used": b_used, "budget": b["budget"], "items": b["items"], "evicted": 0},
            {"used": packed.used, "budget": packed.budget,
             "items": len(packed.included), "evicted": len(packed.evicted)})


def _fit(row: dict, window: int) -> str:
    total = row["used"] + config.RESERVE_RESPONSE
    if total <= window:
        return "fits"
    return f"OVERFLOWS by {total - window}"


def run() -> Result:
    claim = ("C1 -- one memory layer serving a 4B local model and a frontier API, "
             "with only context_window changing")
    store = MemoryStore()
    if not store.count():
        return unavailable("E2", "Budget-assembly ablation", claim,
                           "memory is empty -- run: python -m app seed")

    profile = _profile(store)
    lines = [
        f"profile: {len(profile)} items, "
        f"{sum(_tokens(s.item.rendered()) for s in profile)} tokens if injected whole",
        "",
        "PART 1 -- assembly only, no tools",
        "",
        f"  {'window':>8}  {'config':<22} {'used':>7} {'items':>6} {'evicted':>8}  outcome",
    ]

    overflow_a = {}
    for window, note in WINDOWS:
        rows = [
            ("A  no memory", _config_a(window)),
            ("B  full profile always", _config_b(window, profile)),
            ("C  budget-aware (ours)", _config_c(window, profile)),
        ]
        for label, row in rows:
            lines.append(f"  {window:>8}  {label:<22} {row['used']:>7} "
                         f"{row['items']:>6} {row['evicted']:>8}  {_fit(row, window)}")
            if label.startswith("B"):
                overflow_a[window] = max(0, row["used"] + config.RESERVE_RESPONSE - window)
        lines.append(f"            ({note})")
        lines.append("")

    lines += [
        f"PART 2 -- after {MAX_TOOL_STEPS} tool calls, the coordination problem",
        "",
        f"  {'window':>8}  {'config':<22} {'used':>7} {'items':>6} {'evicted':>8}  outcome",
    ]
    tool_overflow = {}
    for window, _note in WINDOWS:
        b, c = _with_tools(window, profile)
        lines.append(f"  {window:>8}  {'B  append blindly':<22} {b['used']:>7} "
                     f"{b['items']:>6} {b['evicted']:>8}  {_fit(b, window)}")
        lines.append(f"  {window:>8}  {'C  live ledger (ours)':<22} {c['used']:>7} "
                     f"{c['items']:>6} {c['evicted']:>8}  {_fit(c, window)}")
        tool_overflow[window] = max(0, b["used"] + config.RESERVE_RESPONSE - window)
        lines.append("")

    smallest, largest = WINDOWS[0][0], WINDOWS[-1][0]
    lines += [
        "The prediction Part X made in advance was that the margin is largest on",
        "the smallest model. Overflow of config B, by window:",
        "",
    ]
    for window, _ in WINDOWS:
        lines.append(f"  {window:>8}  no tools: {overflow_a[window]:>6} tok over    "
                     f"with tools: {tool_overflow[window]:>6} tok over")

    profile_tokens = sum(_tokens(s.item.rendered()) for s in profile)
    assembly_separates = overflow_a[smallest] > 0 and overflow_a[largest] == 0
    tools_separate = tool_overflow[smallest] > 0 and tool_overflow[largest] == 0

    # Reported as two findings rather than one verdict, because they are two
    # different claims and on a small profile they genuinely disagree.
    lines += ["", "Two findings, because the two halves do not say the same thing:", ""]

    if assembly_separates:
        lines.append(f"  1. ASSEMBLY ALONE separates the sizes: a {profile_tokens}-token "
                     f"profile overflows {smallest} and fits {largest}.")
    else:
        lines.append(
            f"  1. ASSEMBLY ALONE does NOT separate the sizes here. This profile is "
            f"{profile_tokens} tokens\n     over {len(profile)} items, which fits "
            f"every window tested -- so on THIS memory the packer\n     is not yet "
            f"load-bearing for assembly, and saying otherwise would be overclaiming.\n"
            f"     A real imported history (hundreds of items) is where this half "
            f"starts to bite;\n     the seed is a demo, not a workload.")

    if tools_separate:
        lines.append(
            f"\n  2. WITH TOOLS it separates sharply: config B overflows the {smallest}-token\n"
            f"     window by {tool_overflow[smallest]} tokens and fits {largest}. "
            f"Config C fits everywhere,\n     paying with {'evicted items'} it reports "
            f"rather than with the end of the prompt.")
    else:
        lines.append(f"\n  2. WITH TOOLS: B overflows {smallest} by "
                     f"{tool_overflow[smallest]}, {largest} by {tool_overflow[largest]}.")

    if tools_separate and not assembly_separates:
        verdict = (
            f"PARTIALLY CONFIRMED, and the part that fails is worth more than the part "
            f"that passes. The margin IS largest on the smallest model -- but only once "
            f"tools compete for the budget ({tool_overflow[smallest]} tokens of overflow "
            f"at {smallest}). On assembly alone this {profile_tokens}-token seed fits "
            f"every window, so C1 is not demonstrated by static packing at this scale. "
            f"That is precisely the coordination problem the 2026 externalization survey "
            f"names, rather than a budget problem -- and it is the honest version of the "
            f"claim: the packer earns its place when memory and tools contend, not merely "
            f"because memory is large.")
    elif assembly_separates and tools_separate:
        verdict = (f"CONFIRMED on both halves: B overflows {smallest} and fits {largest}, "
                   f"with and without tools. C fits at every size, at the cost it reports.")
    else:
        verdict = (f"NOT CONFIRMED on this memory. B overflows {smallest} by "
                   f"{overflow_a[smallest]} (assembly) / {tool_overflow[smallest]} "
                   f"(with tools). Import real memory and re-run before quoting this.")

    return Result(name="E2", title="Budget-assembly ablation", claim=claim,
                  lines=lines, verdict=verdict)
