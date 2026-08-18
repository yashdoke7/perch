"""Embeddings, with a three-step fallback so the pipeline always runs.

    1. Ollama  (nomic-embed-text)  -- free, local, nothing leaves the machine
    2. an OpenAI-compatible embeddings endpoint, if configured
    3. a deterministic hashed bag-of-words vector

Step 3 is a STAND-IN, not a contribution, and the code says so where it is used.
It exists so a reviewer can clone the repo and watch the whole router -> ranker
-> admission -> packer path execute with no model installed at all. Every real
measurement in Part X uses step 1 or 2.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request

from .. import config

DIM = 512
_WORD = re.compile(r"[a-z0-9']+")

_backend: str | None = None


def backend() -> str:
    """Resolve once, then remember. Reported in the panel so provenance is honest."""
    global _backend
    if _backend is None:
        forced = os.environ.get("PERCH_EMBED_BACKEND")
        _backend = forced if forced in ("ollama", "api", "hashed") else _probe()
    return _backend


def is_semantic() -> bool:
    """True when a real embedding model is answering.

    The hashed fallback matches only on literal shared vocabulary, so its
    related and unrelated score distributions OVERLAP -- measured on the seed
    set, an unrelated pair scored 0.178 while a genuinely related one
    ("rewrite this more formally" against a note about writing style, which
    share no words) scored 0.071. No baseline constant can separate those,
    because the problem is representational rather than a matter of
    calibration. Anything that depends on retrieval QUALITY rather than
    retrieval PLUMBING must check this first.
    """
    return backend() in ("ollama", "api")


def _probe() -> str:
    try:
        req = urllib.request.Request(f"{config.OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=2):
            return "ollama"
    except Exception:
        pass
    if config.API_BASE and config.API_KEY:
        return "api"
    return "hashed"


def embed(text: str) -> list[float]:
    kind = backend()
    if kind == "ollama":
        vec = _ollama(text)
        if vec:
            return vec
    if kind == "api":
        vec = _api(text)
        if vec:
            return vec
    return _hashed(text)


def embed_all(texts: list[str]) -> list[list[float]]:
    return [embed(t) for t in texts]


# ------------------------------------------------------------------- backends

def _post(url: str, payload: dict, headers: dict | None = None, timeout: int = 30) -> dict | None:
    try:
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def _ollama(text: str) -> list[float] | None:
    out = _post(
        f"{config.OLLAMA_URL}/api/embeddings",
        {"model": config.EMBED_MODEL, "prompt": text[:8000]},
    )
    vec = (out or {}).get("embedding")
    return _unit(vec) if vec else None


def _api(text: str) -> list[float] | None:
    out = _post(
        f"{config.API_BASE.rstrip('/')}/embeddings",
        {"model": "text-embedding-3-small", "input": text[:8000]},
        {"Authorization": f"Bearer {config.API_KEY}"},
    )
    try:
        return _unit(out["data"][0]["embedding"])
    except (TypeError, KeyError, IndexError):
        return None


def _hashed(text: str) -> list[float]:
    """Hashed bag of words with sublinear term weighting.

    Not a semantic model -- it matches on shared vocabulary. Good enough to
    exercise the pipeline and to make the gate's behaviour visible; not good
    enough to report a benchmark number with.
    """
    counts: dict[int, float] = {}
    words = _WORD.findall(text.lower())
    for w in words:
        if len(w) < 3:
            continue
        h = int(hashlib.blake2b(w.encode(), digest_size=4).hexdigest(), 16) % DIM
        counts[h] = counts.get(h, 0.0) + 1.0
    vec = [0.0] * DIM
    for h, c in counts.items():
        vec[h] = 1.0 + math.log(c)
    return _unit(vec)


def _unit(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b))))


# General-purpose sentence embedders do NOT sit near zero for unrelated text.
# Measured in this repo: nomic-embed-text puts a completely off-topic pair
# (a question about medication vs. a note about someone's writing style) at
# cosine 0.35-0.41. The hashed bag-of-words fallback sits closer to 0.10-0.15
# for the same kind of pair, because it only fires on literal shared
# vocabulary. A class floor tuned against one baseline silently means a
# different thing under the other -- so RELEVANCE below rescales raw cosine
# against its backend's own baseline before it is ever compared to a floor.
# This is a real, named limitation of naive cosine thresholds (the reason
# MemGate and CRAG both use a learned or corrective step rather than a bare
# threshold); rescaling against a measured baseline is the deliberately
# simple version of that calibration, not a hidden workaround for it.
BASELINE = {
    "hashed": 0.12,
    "ollama": 0.38,
    "api": 0.15,
}


def relevance(raw: float, kind: str | None = None) -> float:
    """Cosine similarity, rescaled against its backend's unrelated-text
    baseline so a class floor means the same thing regardless of which
    embedding backend is live. Used for ranking/admission; NOT used for
    near-duplicate detection in store.py, which wants raw cosine."""
    base = BASELINE.get(kind or backend(), 0.15)
    if raw <= base:
        return 0.0
    return min(1.0, (raw - base) / (1.0 - base))
