"""Model registry and routing (architecture §7.1-7.2).

Every entry carries context_window, and that single field is what makes the
packer model-agnostic: swap the model and the budget recomputes, nothing else
in the system changes. That is Contribution 1 in one line of data.

Routing order: local first. Local is the DEFAULT, not a fallback -- and in
private mode it is the only option, enforced here rather than trusted upstream.
"""

from __future__ import annotations

import json
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


def _ollama_up() -> bool:
    try:
        with urllib.request.urlopen(f"{config.OLLAMA_URL}/api/tags", timeout=2):
            return True
    except Exception:
        return False


def available() -> list[Model]:
    models: list[Model] = []
    if _ollama_up():
        models.append(Model(
            key="local", provider="ollama", model_id=config.LOCAL_MODEL,
            # Conservative: a 3B served by Ollama defaults well below its
            # advertised maximum, and overstating it truncates answers.
            context_window=8192, local=True,
            # Ollama's /api/chat accepts an OpenAI-shaped "tools" list for
            # models that support function calling (the Qwen and Llama
            # families do). Declaring it here is what makes the tool loop
            # -- and therefore memory_search, web_search, file tools -- run
            # for a purely local, ₹0 setup, not only when a cloud key is set.
            tools=True,
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
