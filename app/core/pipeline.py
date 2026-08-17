"""★ The whole request path, in one file (architecture Part VIII).

    capture -> privacy -> intent -> route -> retrieve -> rank -> ADMIT
            -> pack -> model (+ tool loop) -> answer + provenance

Read this file and PERCH_OS_PRIMER.md §5.2 together and you have the system.
Every stage records what it did into a Trace, which the panel renders and the
console prints -- the log IS the architecture, made visible.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .. import config
from ..memory import classes as mc
from ..memory import embed
from ..memory.schema import Scored
from ..memory.store import MemoryStore
from ..models import client, registry
from ..tools import registry as toolreg
from . import admission, packer, privacy, ranker, router


@dataclass
class Request:
    question: str
    selection: str = ""
    source_app: str = ""
    source_title: str = ""
    source_path: str = ""
    private_toggle: bool = False
    prefer_route: str | None = None
    history: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class Trace:
    intent: str = ""
    eligible: list[str] = field(default_factory=list)
    candidates: int = 0
    admitted: list[Scored] = field(default_factory=list)
    dropped: list[Scored] = field(default_factory=list)
    rejected_classes: dict[str, str] = field(default_factory=dict)
    abstained: bool = False
    privacy: str = ""
    private: bool = False
    model: str = ""
    budget: str = ""
    tools: list[str] = field(default_factory=list)
    ms: int = 0

    def lines(self) -> list[str]:
        out = [
            f"intent    {self.intent}",
            f"classes   {', '.join(self.eligible) or '(none)'}",
            f"retrieved {self.candidates} candidates",
        ]
        for cls_name, why in self.rejected_classes.items():
            out.append(f"  x {cls_name}: {why}")
        for s in self.admitted:
            out.append(f"  + [{s.item.cls}] {s.item.title}  ({s.score:.3f})")
        for s in self.dropped[:5]:
            out.append(f"  - [{s.item.cls}] {s.item.title}  ({s.score:.3f}) {s.reason}")
        if self.abstained:
            out.append("  ABSTAINED - nothing cleared its class floor")
        out += [
            f"privacy   {self.privacy}",
            f"model     {self.model}",
            f"budget    {self.budget}",
        ]
        if self.tools:
            out.append(f"tools     {', '.join(self.tools)}")
        out.append(f"elapsed   {self.ms} ms")
        return out


@dataclass
class Response:
    answer: str
    trace: Trace


class Pipeline:
    def __init__(self, store: MemoryStore | None = None) -> None:
        self.store = store or MemoryStore()
        toolreg.bind_memory(self.store)

    def run(self, req: Request) -> Response:
        started = time.time()
        trace = Trace()

        # --- 1. privacy, BEFORE anything reaches a model ---------------------
        decision = privacy.decide(
            req.private_toggle, req.source_app, req.source_title, req.source_path
        )

        # --- 2. intent + class routing ---------------------------------------
        intent = router.resolve(req.question, req.selection, req.source_app, req.source_path)
        trace.intent = intent.describe()
        trace.eligible = intent.eligible

        # --- 3. retrieve -> 4. rank -> 5. admit ------------------------------
        query = f"{req.question}\n{req.selection[:1200]}"
        qvec = embed.embed(query)

        # Routing is PERMISSIVE, admission is STRICT -- deliberately, because
        # the two fail differently. A router that wrongly excludes a class fails
        # SILENTLY: you never learn what you missed. A gate that wrongly drops
        # an item fails VISIBLY: it abstains and says so. So the strictness
        # belongs in the gate, and the router widens itself with a cheap
        # semantic probe over the classes its lexical cues did not reach.
        eligible = list(intent.eligible)
        if not intent.transform_only:
            for cls_name in self._probe(qvec, exclude=eligible):
                eligible.append(cls_name)
        trace.eligible = eligible

        candidates = self.store.candidates(eligible, qvec, config.OVERFETCH)
        trace.candidates = len(candidates)

        ranked = ranker.rank(candidates, req.question, req.selection)
        result = admission.admit(ranked)

        trace.admitted = result.admitted
        trace.dropped = result.dropped
        trace.rejected_classes = result.classes_rejected
        trace.abstained = result.abstained

        # --- 6. the class-driven privacy rule --------------------------------
        # Falls out of the type system for free: if the gate admitted a health
        # or personal item, this request never touches the network.
        if result.forces_local and not decision.private:
            decision = privacy.Decision(
                True, f"admitted {'/'.join(result.private_classes())} memory"
            )
        trace.private = decision.private
        trace.privacy = decision.badge()

        # --- 7. model selection ----------------------------------------------
        model = registry.select(private=decision.private, prefer=req.prefer_route)
        trace.model = model.label()

        # --- 8. pack into the budget -----------------------------------------
        allow_network = not decision.private
        packed = packer.pack(
            question=req.question,
            selection=req.selection,
            admitted=result.admitted,
            context_window=model.context_window,
            history=req.history,
            abstained=result.abstained,
            tools_declared=model.tools and allow_network,
        )
        trace.budget = packed.summary()
        for s in packed.evicted:
            trace.dropped.append(s)
        trace.admitted = packed.included

        # --- 9. generate, with the tool loop ---------------------------------
        tool_log: list[str] = []
        answer = client.complete_with_tools(
            model, packed.system, packed.prompt, allow_network, tool_log
        )
        trace.tools = tool_log

        # --- 10. accounting ---------------------------------------------------
        for s in packed.included:
            self.store.touch(s.item.id)

        trace.ms = int((time.time() - started) * 1000)
        return Response(answer=answer, trace=trace)

    def _probe(self, qvec: list[float], exclude: list[str]) -> list[str]:
        """Cheap semantic widening of the eligible set.

        Looks at the single best item in each class the lexical router did not
        already pick, and admits the CLASS (not the item) if it is plausibly
        related. The admission gate still has to clear it afterwards, so a
        generous probe cannot inject anything on its own.
        """
        widened = []
        for cls_name in mc.ORDER:
            if cls_name in exclude:
                continue
            hits = self.store.candidates([cls_name], qvec, 1)
            if hits and hits[0][1] >= config.PROBE_FLOOR:
                widened.append(cls_name)
        return widened
