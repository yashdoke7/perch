"""
Minimal model routing (§4.6), enough to prove the loop end-to-end.

Order of preference:
    1. Ollama on localhost  — free, no key, nothing leaves the machine
    2. an OpenAI-compatible endpoint if PERCH_API_BASE / PERCH_API_KEY are set
    3. an offline echo stub so the OS layer can be demonstrated with no model at all

The real product's registry also carries context_window per model, which is what
Layer 2 uses to size the budget. Out of scope for this demo.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = os.environ.get("PERCH_LOCAL_MODEL", "qwen2.5:3b")

SYSTEM = (
    "You are PERCH, a concise desktop assistant. The user selected some text in "
    "another application and asked about it. Answer directly. If they ask you to "
    "rewrite the selection, reply with ONLY the rewritten text and nothing else."
)


def _post(url: str, payload: dict, headers: dict | None = None, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def _try_ollama(question: str, selection: str) -> str | None:
    prompt = f"{SYSTEM}\n\nSELECTED TEXT:\n{selection}\n\nQUESTION:\n{question}\n\nANSWER:"
    try:
        result = _post(
            OLLAMA_URL,
            {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        )
        return (result.get("response") or "").strip() or None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    except Exception:
        return None


def _try_openai_compatible(question: str, selection: str) -> str | None:
    base = os.environ.get("PERCH_API_BASE")
    key = os.environ.get("PERCH_API_KEY")
    model = os.environ.get("PERCH_API_MODEL", "gpt-4o-mini")
    if not base or not key:
        return None
    try:
        result = _post(
            f"{base.rstrip('/')}/chat/completions",
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": f"SELECTED TEXT:\n{selection}\n\nQUESTION:\n{question}",
                    },
                ],
            },
            headers={"Authorization": f"Bearer {key}"},
        )
        return result["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def ask(question: str, selection: str) -> str:
    """Route the request. Local first — that is the default, not a fallback."""
    for backend, label in ((_try_ollama, "local"), (_try_openai_compatible, "cloud")):
        answer = backend(question, selection)
        if answer:
            print(f"[model] answered via {label}")
            return answer

    return (
        "(no model reachable — OS layer still proven)\n\n"
        f"You asked: {question}\n"
        f"Captured {len(selection)} characters of selection.\n\n"
        "Start Ollama (`ollama run qwen2.5:3b`) or set PERCH_API_BASE and "
        "PERCH_API_KEY to get a real answer. Replace / Insert / Copy work either way."
    )
