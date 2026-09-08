"""Model registry and routing (architecture §7.1-7.2).

Every entry carries context_window, and that single field is what makes the
packer model-agnostic: swap the model and the budget recomputes, nothing else
in the system changes. That is Contribution 1 in one line of data.

Routing order: local first. Local is the DEFAULT, not a fallback -- and in
private mode it is the only option, enforced here rather than trusted upstream.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .. import config


@dataclass
class Model:
    key: str
    provider: str          # ollama | openai_compatible | stub
    model_id: str
    context_window: int
    local: bool
    tools: bool = False
    vision: bool = False

    def label(self) -> str:
        where = "local" if self.local else "cloud"
        return f"{self.model_id} ({where}, {self.context_window} tok)"


STUB = Model(key="stub", provider="stub", model_id="offline-stub",
             context_window=8192, local=True)


# The probe result, cached briefly. Ollama starting or stopping mid-session is
# rare; paying for the check on every request is not.
PROBE_TTL = 30.0
_probe: tuple[float, bool] | None = None


def _ollama_up() -> bool:
    """Is a local Ollama reachable? Cached, because this used to be per-request.

    available() is called on EVERY request, and this probe blocks for up to
    two seconds when nothing is listening. So on a machine without Ollama --
    which is exactly the machine the offline story is aimed at -- every panel
    request stalled two seconds before falling through to the stub, and the
    delay landed inside model selection where no stage timer could see it.
    E6 caught it: 20 timed runs took 40 seconds, and the "retrieval latency"
    it reported was almost entirely this timeout.

    A 30-second TTL keeps a started-Ollama discoverable without a restart
    while making the steady-state cost zero.
    """
    global _probe
    now = time.monotonic()
    if _probe is not None and now - _probe[0] < PROBE_TTL:
        return _probe[1]
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=2):
            up = True
    except Exception:
        up = False
    _probe = (now, up)
    return up


def forget_probe() -> None:
    """Drop the cached probe. For tests, and for `models` which should always
    report what is true right now rather than what was true 30 seconds ago."""
    global _probe
    _probe = None


_meta: dict[str, dict] = {}


def model_meta(model_id: str) -> dict:
    """Ask Ollama what this model can actually do, rather than assuming.

    /api/show reports `capabilities` (completion / tools / vision) and the
    model's true context length. Both were previously hardcoded: every local
    model was declared tools=True regardless, which breaks the tool loop on a
    model that cannot call one, and vision was never available locally at all.

    Cached, because available() is called on every request.
    """
    if model_id in _meta:
        return _meta[model_id]

    caps: set[str] = set()
    max_ctx = 0
    try:
        req = urllib.request.Request(
            f"{config.OLLAMA_URL}/api/show",
            data=json.dumps({"model": model_id}).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        caps = set(data.get("capabilities") or [])
        for key, value in (data.get("model_info") or {}).items():
            if key.endswith(".context_length") and isinstance(value, int):
                max_ctx = max(max_ctx, value)
    except Exception:
        # An unreachable or older Ollama: assume the conservative defaults
        # that were hardcoded before, rather than declaring nothing.
        caps = {"completion", "tools"}

    _meta[model_id] = {"capabilities": caps, "max_context": max_ctx}
    return _meta[model_id]


def forget_meta() -> None:
    _meta.clear()


def available() -> list[Model]:
    models: list[Model] = []
    if _ollama_up():
        meta = model_meta(config.LOCAL_MODEL)
        caps = meta["capabilities"]
        # The window we will actually REQUEST -- see config.NUM_CTX and
        # client._ollama_options(). Capped by what the model can do, because
        # asking for more than its trained length is how you get nonsense.
        ceiling = meta["max_context"] or config.NUM_CTX
        models.append(Model(
            key="local", provider="ollama", model_id=config.LOCAL_MODEL,
            context_window=min(config.NUM_CTX, ceiling), local=True,
            tools="tools" in caps,
            vision="vision" in caps,
        ))
    if config.API_BASE and config.API_KEY:
        models.append(Model(
            key="cloud", provider="openai_compatible", model_id=config.API_MODEL,
            context_window=128_000, local=False, tools=True, vision=True,
        ))
    models.append(STUB)
    return models


def select(private: bool, prefer: str | None = None) -> Model:
    models = available()

    if private:
        # Enforced here, not trusted upstream. A private request that silently
        # reaches a cloud endpoint is the one failure that makes the whole
        # privacy story worthless.
        local = [m for m in models if m.local]
        return local[0]

    want = prefer or config.DEFAULT_ROUTE
    if want == "local":
        for m in models:
            if m.local and m.provider != "stub":
                return m
    if want == "cloud":
        for m in models:
            if not m.local:
                return m

    # auto: real local model, then cloud, then stub
    for m in models:
        if m.provider == "ollama":
            return m
    for m in models:
        if not m.local:
            return m
    return STUB
