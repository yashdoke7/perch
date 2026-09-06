"""E5 — privacy: zero bytes leave the machine in private mode.

Part X specifies this as *"bytes leaving the machine in private mode = 0, by
packet capture"*. This is not a packet capture, and the difference is stated
here rather than glossed, because overstating a privacy guarantee is worse
than not testing it.

    What this does          instruments socket.socket.connect for the duration
                            of a real private-mode request, and records every
                            address this process tries to reach.

    What that proves        no code path inside PERCH's own process opened a
                            connection to anything but loopback.

    What it does NOT prove  that no bytes left the machine. A subprocess would
                            not be seen (run_python spawns one), nor would a
                            DNS lookup performed by a library that resolves
                            before connecting, nor anything a dependency does
                            through a handle it opened earlier.

> **So this is a necessary condition, not the sufficient one.** It is
> automatable, runs on every machine, and catches the realistic regression --
> someone wiring a new tool or an embedding call without checking the privacy
> decision. The packet capture remains the claim to make on a slide, and it
> remains unrun.

The two failure modes it is actually built to catch:

  1. a network TOOL being reachable in private mode -- covered by the tool
     schema test too, but this catches it at the socket rather than the
     declaration, so a tool that bypasses `schemas()` is still caught
  2. an EMBEDDING call going to a cloud endpoint. This one is easy to miss:
     the request is private, the model is local, and retrieval still quietly
     posts the query to an OpenAI-compatible embeddings API because that is
     what the embed backend happened to resolve to.
"""

from __future__ import annotations

import socket

from ..core.pipeline import Pipeline, Request
from ..memory.store import MemoryStore
from .harness import Result, unavailable

LOOPBACK_PREFIXES = ("127.", "::1", "localhost")


def _is_local(address) -> bool:
    try:
        host = address[0] if isinstance(address, tuple) else str(address)
    except Exception:                                     # noqa: BLE001
        return False
    host = str(host)
    return any(host.startswith(p) or host == p for p in LOOPBACK_PREFIXES)


class _Recorder:
    """Wrap socket.connect for the duration of a request.

    Patching the class method rather than the module means anything that
    already imported socket is still caught -- urllib holds its own reference
    to the module, so patching `socket.socket` itself would miss it.
    """

    def __init__(self) -> None:
        self.attempts: list[str] = []
        self._original = None

    def __enter__(self) -> "_Recorder":
        self._original = socket.socket.connect
        recorder = self

        def connect(sock_self, address, *a, **kw):
            recorder.attempts.append(
                f"{address}  {'local' if _is_local(address) else 'REMOTE'}")
            return recorder._original(sock_self, address, *a, **kw)

        socket.socket.connect = connect
        return self

    def __exit__(self, *exc) -> None:
        socket.socket.connect = self._original

    @property
    def remote(self) -> list[str]:
        return [a for a in self.attempts if "REMOTE" in a]


def run() -> Result:
    claim = "§7.3 -- in private mode, zero bytes leave the machine"
    store = MemoryStore()
    if not store.count():
        return unavailable("E5", "Privacy: zero egress in private mode", claim,
                           "memory is empty -- run: python -m app seed")

    pipeline = Pipeline(store)
    lines = [
        "Method: socket.socket.connect is instrumented for the duration of one",
        "real private-mode request through the full pipeline. Every address this",
        "process tries to reach is recorded and classified.",
        "",
    ]

    # A question with health cues, so the class-driven rule (§7.3 mechanism 4)
    # has something to fire on as well as the explicit toggle.
    question = "what should I ask the doctor about my medication?"

    with _Recorder() as rec:
        response = pipeline.run(Request(question=question, private_toggle=True))

    lines += [
        f"request:  {question!r}  (Private switch ON)",
        f"decision: {response.trace.privacy}",
        f"model:    {response.trace.model}",
        f"tools:    {', '.join(response.trace.tools) or '(none called)'}",
        "",
        f"connection attempts during the request: {len(rec.attempts)}",
    ]
    for attempt in rec.attempts[:12]:
        lines.append(f"    {attempt}")
    if not rec.attempts:
        lines.append("    (none -- nothing opened a socket at all)")

    passed = not rec.remote and response.trace.private
    lines += [
        "",
        f"remote connections: {len(rec.remote)}",
    ]
    for r in rec.remote:
        lines.append(f"    !! {r}")

    lines += [
        "",
        "What this does not cover, stated so the claim is not overread:",
        "  - a subprocess (run_python spawns one) is invisible to this",
        "  - a connection opened before the request began is invisible to this",
        "  - this is a necessary condition for the Part X claim, not the",
        "    packet capture itself, which remains unrun",
    ]

    if not response.trace.private:
        verdict = ("INCONCLUSIVE: the request was not treated as private, so this "
                   "measured nothing. That is itself a failure -- investigate before "
                   "reading anything else here.")
    elif passed:
        verdict = ("PASSED (necessary condition): the request was routed locally and "
                   "this process opened no remote connection. The packet capture is "
                   "still the claim to make publicly.")
    else:
        verdict = (f"FAILED: {len(rec.remote)} remote connection(s) during a private "
                   f"request. This is the one failure that makes the whole privacy "
                   f"story worthless -- fix before anything else.")

    return Result(name="E5", title="Privacy: zero egress in private mode",
                  claim=claim, lines=lines, verdict=verdict)
