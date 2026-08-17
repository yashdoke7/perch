"""Talking to whichever model the registry picked, plus the agent tool loop.

The tool loop is what makes PERCH an agent rather than a prompt template:

    model -> tool call -> result -> model -> ... -> answer

Each tool result re-enters the budget, which is why tools and memory are
charged against the same allowance in packer.py.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .. import config
from ..tools import registry as toolreg
from .registry import Model

MAX_TOOL_STEPS = 4


def _post(url: str, payload: dict, headers: dict | None = None, timeout: int = 120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def complete(model: Model, system: str, prompt: str) -> str:
    """One shot, no tools. Used by the local path and by the extractor."""
    if model.provider == "ollama":
        try:
            out = _post(f"{config.OLLAMA_URL}/api/generate", {
                "model": model.model_id,
                "prompt": f"{system}\n\n{prompt}",
                "stream": False,
            })
            return (out.get("response") or "").strip()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return f"(local model unreachable: {exc})"

    if model.provider == "openai_compatible":
        try:
            out = _post(f"{config.API_BASE.rstrip('/')}/chat/completions", {
                "model": model.model_id,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            }, {"Authorization": f"Bearer {config.API_KEY}"})
            return out["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            return f"(cloud model failed: {exc})"

    return _stub(prompt)


def complete_with_tools(model: Model, system: str, prompt: str,
                        allow_network: bool, log: list[str]) -> str:
    """The agent loop. Only the cloud path advertises tool calling today."""
    if model.provider != "openai_compatible" or not model.tools:
        return complete(model, system, prompt)

    schemas = toolreg.schemas(allow_network=allow_network)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    for _ in range(MAX_TOOL_STEPS):
        try:
            out = _post(f"{config.API_BASE.rstrip('/')}/chat/completions", {
                "model": model.model_id,
                "messages": messages,
                "tools": schemas,
                "tool_choice": "auto",
            }, {"Authorization": f"Bearer {config.API_KEY}"})
        except Exception as exc:
            return f"(cloud model failed: {exc})"

        choice = out["choices"][0]["message"]
        calls = choice.get("tool_calls") or []
        if not calls:
            return (choice.get("content") or "").strip()

        messages.append(choice)
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = toolreg.dispatch(name, args, allow_network=allow_network)
            log.append(f"{name}({', '.join(f'{k}={v!r}' for k, v in args.items())[:80]})")
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result[:4000],
            })

    return "(tool loop did not converge)"


def _stub(prompt: str) -> str:
    return (
        "(no model reachable - the OS layer, routing, ranking, admission and "
        "packing all still ran; only generation is missing)\n\n"
        "Start Ollama (`ollama run qwen2.5:3b`) or set PERCH_API_BASE and "
        "PERCH_API_KEY for a real answer.\n\n"
        f"--- assembled prompt, {len(prompt)} chars ---\n{prompt[:1200]}"
    )
