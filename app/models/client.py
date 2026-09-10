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

# Floor on what a tool result may be squeezed to before we stop pretending it
# is useful. Below this, a truncated result is noise the model will reason
# from anyway, so it is better to say the result did not fit.
MIN_USEFUL_TOOL_CHARS = 300


def _encode_image(path: str) -> str | None:
    """A screenshot as base64, the way Ollama wants it on a message.

    Returns None rather than raising: a capture that vanished between the drag
    and the request is a reason to answer without it, not to lose the request.
    """
    import base64
    from pathlib import Path as _Path
    try:
        return base64.b64encode(_Path(path).read_bytes()).decode("ascii")
    except OSError:
        return None


def _charge_tool_result(packed, result: str, on_evict=None) -> str:
    """★ Contribution 1, at the only point where it is actually testable.

    Tools and memory compete for ONE allowance. The packer spent the budget
    before generation started; a tool result arriving afterwards must be paid
    for out of the same pot, and the only currency left is memory the ranker
    already judged least useful.

    Three outcomes, in order of preference:

        1. it fits            -> charge it, nothing changes
        2. it does not fit    -> evict the lowest-ranked memory to make room
        3. still does not fit -> truncate the result and SAY SO in the text,
                                 so the model knows it is reasoning from a
                                 fragment rather than silently assuming it
                                 has the whole thing

    Without this, complete_with_tools appended result[:4000] and hoped. With
    a 4-step loop against an 8192-token local model that overflows the window
    by roughly 2300 tokens -- the model then truncates the prompt from the
    far end, which is where the system prompt and the memory live. The
    failure looks like the model ignoring its instructions.
    """
    if packed is None:                       # callers that do not budget (tests, tools off)
        return result[:4000]

    cost = int(len(result) / config.CHARS_PER_TOKEN) + 1
    if cost > packed.headroom:
        thrown = packed.make_room(cost - packed.headroom)
        if thrown and on_evict:
            on_evict(thrown)

    if cost > packed.headroom:
        keep = max(0, int(packed.headroom * config.CHARS_PER_TOKEN) - 80)
        if keep < MIN_USEFUL_TOOL_CHARS:
            return ("[tool result omitted: no context budget left for it. "
                    "Answer from what you already have, or say you could not "
                    "retrieve it -- do not invent the contents.]")
        result = result[:keep] + "\n[...truncated: out of context budget...]"

    packed.charge(result)
    return result


def _refresh_prompt(messages: list[dict], packed) -> None:
    """Push an evicted prompt back into the conversation.

    make_room() rebuilds Packed.prompt without the memory it threw away, but
    the model is reading messages[1] -- the copy taken when the loop started.
    Leaving that stale would make the eviction accounting a lie: we would have
    told the ledger the tokens were freed while still sending them.
    """
    if packed is None or not messages:
        return
    for msg in messages:
        if msg.get("role") == "user":
            msg["content"] = packed.prompt
            return


def _post(url: str, payload: dict, headers: dict | None = None, timeout: int = 120):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _post_lines(url: str, payload: dict, headers: dict | None = None, timeout: int = 180):
    """Yield each JSON object from a line-delimited streaming response.

    Ollama streams newline-delimited JSON objects; OpenAI-compatible
    endpoints stream SSE ('data: {...}' with a '[DONE]' sentinel). Both are
    handled here so the caller just gets dicts.
    """
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
                if line == "[DONE]":
                    return
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _ollama_options(model: Model) -> dict:
    """The options every Ollama call must carry.

    num_ctx is the load-bearing one. Ollama defaults it to 4096 regardless of
    what the model supports, and silently discards anything past it -- from
    the front, where our system prompt and admitted memory live. Without this
    the packer's budget is a number we computed and nobody honoured, which
    makes C1 a claim about arithmetic rather than about the model's context.

    Sending it is what makes registry.Model.context_window true by
    construction instead of by assumption.
    """
    return {"num_ctx": model.context_window}


def complete(model: Model, system: str, prompt: str, image_path: str = "",
             options: dict | None = None) -> str:
    """One shot, no tools. Used by the local path, the extractor and E1.

    `options` adds sampling settings (E1 pins temperature and seed so a
    rerun reproduces). num_ctx still comes from the model and cannot be
    overridden here -- that number is what the budget was computed from.
    """
    if model.provider == "ollama":
        try:
            payload = {
                "model": model.model_id,
                "prompt": f"{system}\n\n{prompt}",
                "stream": False,
                "options": {**(options or {}), **_ollama_options(model)},
            }
            if image_path:
                encoded = _encode_image(image_path)
                if encoded:
                    payload["images"] = [encoded]
            out = _post(f"{config.OLLAMA_URL}/api/generate", payload)
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
                **({"temperature": options["temperature"]}
                   if options and "temperature" in options else {}),
            }, {"Authorization": f"Bearer {config.API_KEY}"})
            return out["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            return f"(cloud model failed: {exc})"

    return _stub(prompt)


def complete_with_tools(model: Model, system: str, prompt: str,
                        allow_network: bool, log: list[str],
                        on_token=None, on_tool=None, on_confirm=None,
                        packed=None, on_evict=None, image_path: str = "") -> str:
    """The agent loop: model -> tool call -> result -> model, until it stops.

    Both routes get the loop, not just the cloud one -- a student running
    Ollama with nothing else configured should still get memory_search,
    file tools and (network permitting) web_search, not a single-shot
    completion with no access to the tool surface described in the
    architecture.

    on_confirm(name, args) -> bool is carried through to dispatch() and is
    what makes "read is free, write asks" real. Passing nothing means
    confirming tools are refused rather than silently allowed.
    """
    if not model.tools:
        return complete(model, system, prompt, image_path=image_path)

    schemas = toolreg.schemas(allow_network=allow_network)
    user_msg: dict = {"role": "user", "content": prompt}
    if image_path:
        encoded = _encode_image(image_path)
        if encoded:
            user_msg["images"] = [encoded]
    messages = [
        {"role": "system", "content": system},
        user_msg,
    ]

    if model.provider == "openai_compatible":
        return _openai_tool_loop(model, messages, schemas, allow_network, log,
                                 on_confirm=on_confirm, packed=packed,
                                 on_evict=on_evict)
    if model.provider == "ollama":
        return _ollama_tool_loop(model, messages, schemas, allow_network, log,
                                 on_token=on_token, on_tool=on_tool,
                                 on_confirm=on_confirm, packed=packed,
                                 on_evict=on_evict)
    return complete(model, system, prompt)


def _openai_tool_loop(model: Model, messages: list[dict], schemas: list[dict],
                      allow_network: bool, log: list[str],
                      on_confirm=None, packed=None, on_evict=None) -> str:
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
            result = toolreg.dispatch(name, args, allow_network=allow_network,
                                      on_confirm=on_confirm)
            log.append(f"{name}({', '.join(f'{k}={v!r}' for k, v in args.items())[:80]})")
            charged = _charge_tool_result(packed, result, on_evict)
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": charged,
            })
            _refresh_prompt(messages, packed)

    return "(tool loop did not converge)"


def _ollama_tool_loop(model: Model, messages: list[dict], schemas: list[dict],
                      allow_network: bool, log: list[str],
                      on_token=None, on_tool=None, on_confirm=None,
                      packed=None, on_evict=None) -> str:
    """Same shape as the OpenAI loop, over /api/chat, but streaming.

    Two differences from the OpenAI path: Ollama has no tool_choice knob,
    and its tool_calls arrive with arguments already as a dict rather than
    a JSON string -- handled below rather than assumed.

    Streaming matters more than it looks for a live demo: a local 3B model
    takes 10-20s to finish, and a frozen window for that long reads as a
    hang. Tokens are emitted through on_token as they arrive. Tool calls
    can also appear mid-stream, so both are accumulated in one pass.
    """
    for _ in range(MAX_TOOL_STEPS):
        content_parts: list[str] = []
        calls: list[dict] = []
        try:
            for chunk in _post_lines(f"{config.OLLAMA_URL}/api/chat", {
                "model": model.model_id,
                "messages": messages,
                "tools": schemas,
                "stream": True,
                "options": _ollama_options(model),
            }):
                msg = chunk.get("message") or {}
                for call in (msg.get("tool_calls") or []):
                    calls.append(call)
                piece = msg.get("content") or ""
                if piece:
                    content_parts.append(piece)
                    if on_token and not calls:
                        # Only surface tokens once we know this turn is a real
                        # answer, not a preamble to a tool call.
                        on_token(piece)
                if chunk.get("done"):
                    break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return f"(local model unreachable: {exc})"

        content = "".join(content_parts).strip()
        if not calls:
            return content

        if packed is not None and content:
            packed.charge(content, kind="turn")
        messages.append({"role": "assistant", "content": content, "tool_calls": calls})
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            if on_tool:
                on_tool(name)
            result = toolreg.dispatch(name, args, allow_network=allow_network,
                                      on_confirm=on_confirm)
            log.append(f"{name}({', '.join(f'{k}={v!r}' for k, v in args.items())[:80]})")
            charged = _charge_tool_result(packed, result, on_evict)
            messages.append({"role": "tool", "content": charged})
            _refresh_prompt(messages, packed)

    return "(tool loop did not converge)"


def _stub(prompt: str) -> str:
    return (
        "(no model reachable - the OS layer, routing, ranking, admission and "
        "packing all still ran; only generation is missing)\n\n"
        "Start Ollama (`ollama run qwen2.5:3b`) or set PERCH_API_BASE and "
        "PERCH_API_KEY for a real answer.\n\n"
        f"--- assembled prompt, {len(prompt)} chars ---\n{prompt[:1200]}"
    )
