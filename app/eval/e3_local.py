"""E3 -- retrieval quality on labelled personas.

    python -m app eval e3

Part X names LongMemEval and LoCoMo for E3. Neither is vendored here, and both
measure long-conversation recall rather than the thing PERCH claims: that the
gate admits what a question needs AND NOTHING ELSE, across six typed classes,
two of them private. So this is a PERCH-written benchmark, labelled as such.

TWO personas, and the split is the point:

    development   probes/persona_retrieval.json   68 memories, 112 questions
                  floors and the margin are FITTED here, by 5-fold CV
    held-out      probes/persona_heldout.json     42 memories, 69 questions
                  NEVER used for fitting -- only scored. This is the number.

Each question is labelled with the memories a good answer needs ('relevant')
and those that would be acceptable context ('ok'), across seven kinds: direct,
paraphrase (no shared keywords), cross-class, abstain (general knowledge),
bait (in-domain but not stored), transform, identity.

Configurations over the same store and ranker:

    A  naive top-4 over every class      what most memory layers do
    B  one global threshold              stops leaks, and loses identity
    C  PERCH as shipped                  routed, per-class floors + margin
    C* fitted on the development set     the answer to self-critique §6

It also runs the memory LIFECYCLE end to end against the real embedder: write,
recall, merge a near-duplicate, edit, rebuild the index from the files alone,
forget. Those are pass/fail, because each is a promise the UI makes.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import tempfile
import time
from pathlib import Path

from .. import config
from ..core import admission, ranker, router
from ..core.pipeline import Pipeline, Request, Trace
from ..memory import classes as mc
from ..memory import embed
from ..memory.schema import MemoryItem
from ..memory.store import MemoryStore
from .harness import Result, unavailable

PROBES = Path(__file__).resolve().parent / "probes"
DEV = PROBES / "persona_retrieval.json"
HELDOUT = PROBES / "persona_heldout.json"
RECORDS = config.ROOT / "eval"
TITLE = "Retrieval quality -- PERCH persona benchmark (not LongMemEval/LoCoMo)"
CLAIM = ("the gate admits what a question needs and nothing else at a realistic "
         "memory size, with floors fitted on one persona and scored on another")

NAIVE_K = 4
GLOBAL_TAU = 0.30
FOLDS = 5
GRID = [round(0.10 + 0.02 * i, 2) for i in range(26)]          # 0.10 .. 0.60
ALPHAS = [round(0.50 + 0.05 * i, 2) for i in range(9)]          # 0.50 .. 0.90
# A tie is not a win: 0.79 against 0.79 once printed SUPPORTS.
WIN_BY = 0.02
KINDS = ["direct", "paraphrase", "cross", "abstain", "bait", "transform"]
NAMES = {"A": f"A naive top-{NAIVE_K}", "B": f"B global tau {GLOBAL_TAU:.2f}",
         "C": "C PERCH as shipped", "C*": "C* fitted on dev"}


# ------------------------------------------------------------------ data

def load(path: str | Path | None = None) -> dict:
    data = json.loads(Path(path or DEV).read_text(encoding="utf-8"))
    keys = {it["key"] for it in data["items"]}
    if len(keys) != len(data["items"]):
        raise ValueError("duplicate item keys")
    for q in data["queries"]:
        for k in q.get("relevant", []) + q.get("ok", []):
            if k not in keys:
                raise ValueError(f"query {q['q']!r} names unknown item {k!r}")
    return data


def build_store(data: dict) -> tuple[MemoryStore, dict[str, str], list[str]]:
    tmp = Path(tempfile.mkdtemp(prefix="perch-e3-"))
    store = MemoryStore(root=tmp / "memory", db=tmp / "index.sqlite3")
    key_to_id: dict[str, str] = {}
    merged: list[str] = []
    for it in data["items"]:
        stored, how = store.add(MemoryItem(
            cls=it["cls"], title=it["title"], body=it["body"],
            tags=list(it.get("tags", [])), entities=list(it.get("entities", [])),
            source_kind="manual"))
        key_to_id[it["key"]] = stored.id
        if how == "merged":
            merged.append(it["key"])
    return store, key_to_id, merged


def shipped_params() -> dict:
    return {"floors": {c: mc.floor_for(c) for c in mc.ORDER}, "alpha": config.MARGIN_ALPHA}


# --------------------------------------------------------------- scoring

def score_query(admitted: list[str], q: dict, private_keys: set[str]) -> dict:
    rel, ok = set(q.get("relevant", [])), set(q.get("ok", []))
    got = set(admitted)
    intrusions = got - rel - ok
    return {"n_rel": len(rel), "hits": len(got & rel), "admitted": len(got),
            "acceptable": len(got & (rel | ok)), "intrusions": sorted(intrusions),
            "missed": sorted(rel - got),
            "private_leak": bool(intrusions & private_keys), "clean": not intrusions}


def summarise(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["n_rel"]]
    unanswerable = [r for r in rows if not r["n_rel"]]
    n_rel = sum(r["n_rel"] for r in answerable)
    recall = sum(r["hits"] for r in answerable) / n_rel if n_rel else 0.0
    admitted = sum(r["admitted"] for r in rows)
    precision = sum(r["acceptable"] for r in rows) / admitted if admitted else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "recall": recall, "precision": precision, "f1": f1,
        "hit_rate": (sum(r["hits"] > 0 for r in answerable) / len(answerable)
                     if answerable else 0.0),
        "abstain_ok": (sum(r["clean"] for r in unanswerable) / len(unanswerable)
                       if unanswerable else 1.0),
        "leaks": sum(r["private_leak"] for r in rows),
        "n": len(rows),
    }


# ------------------------------------------------------------ one persona

class Persona:
    """One labelled persona in its own store, with every question's candidates
    computed once -- so parameters can be refitted without re-embedding."""

    def __init__(self, path: Path, progress=None, label: str = "") -> None:
        self.data = load(path)
        self.queries = self.data["queries"]
        self.store, key_to_id, self.merged = build_store(self.data)
        self.id_to_key = {v: k for k, v in key_to_id.items()}
        self.item_cls = {it["key"]: it["cls"] for it in self.data["items"]}
        self.private = {k for k, c in self.item_cls.items() if mc.is_private_class(c)}
        self.pipeline = Pipeline(self.store)
        self.rows: dict[str, list[dict]] = {"A": [], "B": [], "C": []}
        self.routed: list[tuple[list, bool]] = []
        self.records: list[dict] = []
        self.gate_ms: list[float] = []
        self.rr: list[float] = []
        self.recall4: list[float] = []
        self.mismatches = 0
        shipped = shipped_params()

        for n, q in enumerate(self.queries, 1):
            if progress:
                progress(n, len(self.queries), f"{label} {q['q']}")
            sel = q.get("selection", "")
            qvec = embed.embed(f"{q['q']}\n{sel[:1200]}")
            ranked = ranker.rank(self.store.candidates(list(mc.ORDER), qvec, config.OVERFETCH),
                                 q["q"], sel)
            a = self.keys(ranked[:NAIVE_K])
            b = self.keys([s for s in ranked if s.score >= GLOBAL_TAU])

            started = time.perf_counter()
            gated = self.pipeline._gate(Request(question=q["q"], selection=sel), Trace(),
                                        lambda *_a, **_k: None)
            self.gate_ms.append((time.perf_counter() - started) * 1000)
            c = self.keys(gated.admitted)

            routed = self._routed(qvec, q)
            self.routed.append(routed)
            if sorted(self.admit(len(self.routed) - 1, shipped)) != sorted(c):
                self.mismatches += 1

            for cfg, got in (("A", a), ("B", b), ("C", c)):
                self.rows[cfg].append(score_query(got, q, self.private))
            rel = set(q.get("relevant", []))
            if rel:
                order = self.keys(ranked)
                first = next((i for i, k in enumerate(order, 1) if k in rel), None)
                self.rr.append(1 / first if first else 0.0)
                self.recall4.append(len(set(order[:NAIVE_K]) & rel) / len(rel))
            self.records.append({"q": q["q"], "kind": q["kind"],
                                 "relevant": q.get("relevant", []), "A": a, "B": b, "C": c})

    def keys(self, scored) -> list[str]:
        return [self.id_to_key[s.item.id] for s in scored if s.item.id in self.id_to_key]

    def _routed(self, qvec, q: dict) -> tuple[list, bool]:
        """What the shipped pipeline ranks -- same routing, same probe."""
        intent = router.resolve(q["q"], q.get("selection", ""))
        eligible = list(intent.eligible)
        if not intent.transform_only:
            eligible += self.pipeline._probe(qvec, exclude=eligible)
        ranked = ranker.rank(self.store.candidates(eligible, qvec, config.OVERFETCH),
                             q["q"], q.get("selection", ""))
        return ranked, intent.transform_only

    def admit(self, i: int, params: dict) -> list[str]:
        ranked, voice = self.routed[i]
        return self.keys(admission.admit(ranked, alpha=params["alpha"],
                                         floors=params["floors"], voice_always=voice).admitted)

    def score(self, params: dict, idx: list[int] | None = None) -> list[dict]:
        idx = range(len(self.queries)) if idx is None else idx
        return [score_query(self.admit(i, params), self.queries[i], self.private) for i in idx]

    def fit(self, start: dict, idx: list[int] | None = None) -> dict:
        """Coordinate descent over the six floors and the margin.

        Objective, lexicographic: fewest private leaks first -- the one error
        the design says must not happen -- then F1 plus half the abstention
        accuracy, so a floor cannot buy recall by admitting on everything.
        """
        def objective(params):
            s = summarise(self.score(params, idx))
            return (-s["leaks"], round(s["f1"] + 0.5 * s["abstain_ok"], 6))

        params = {"floors": dict(start["floors"]), "alpha": start["alpha"]}
        best = objective(params)
        for _ in range(4):
            changed = False
            for cls_name in mc.ORDER:
                for value in GRID:
                    trial = {"floors": {**params["floors"], cls_name: value},
                             "alpha": params["alpha"]}
                    s = objective(trial)
                    if s > best:
                        best, params, changed = s, trial, True
            for value in ALPHAS:
                trial = {"floors": params["floors"], "alpha": value}
                s = objective(trial)
                if s > best:
                    best, params, changed = s, trial, True
            if not changed:
                break
        return params

    def kinds(self, cfg_rows: dict[str, list[dict]], a: str, b: str) -> list[str]:
        out = []
        for kind in KINDS + ["identity"]:
            if kind == "identity":
                idx = [i for i, q in enumerate(self.queries) if q.get("relevant") and all(
                    self.item_cls[k] == "identity" for k in q["relevant"])]
            else:
                idx = [i for i, q in enumerate(self.queries) if q["kind"] == kind]
            if not idx:
                continue
            sa = summarise([cfg_rows[a][i] for i in idx])
            sb = summarise([cfg_rows[b][i] for i in idx])
            out.append(f"    {kind:<11}{len(idx):>4} q   F1 {sa['f1']:.2f} -> {sb['f1']:.2f}"
                       f"   abstain {sa['abstain_ok']:.2f} -> {sb['abstain_ok']:.2f}"
                       f"   leaks {sa['leaks']} -> {sb['leaks']}")
        return out


def table(stats: dict[str, dict], order: list[str]) -> list[str]:
    out = [f"  {'config':<24}{'recall':>7}{'hit':>7}{'prec':>7}{'F1':>7}{'abstain':>9}{'leaks':>7}"]
    for cfg in order:
        s = stats[cfg]
        out.append(f"  {NAMES[cfg]:<24}{s['recall']:>7.2f}{s['hit_rate']:>7.2f}"
                   f"{s['precision']:>7.2f}{s['f1']:>7.2f}{s['abstain_ok']:>9.2f}{s['leaks']:>7}")
    return out


# ------------------------------------------------------------- lifecycle

def lifecycle(store: MemoryStore, pipeline: Pipeline) -> list[tuple[str, bool, str]]:
    """Each promise the Memory screen makes, checked against the real embedder."""
    checks: list[tuple[str, bool, str]] = []
    question = "when are my gym sessions?"

    def recalled() -> list[MemoryItem]:
        return [s.item for s in pipeline.preview(question).admitted]

    item, how = store.add(MemoryItem(
        cls="personal", title="Gym membership", tags=["gym", "fitness"],
        body="Joined Cult.fit in Koramangala on a 6-month plan; sessions Monday, "
             "Wednesday and Friday at 6:30am.", source_kind="manual"))
    checks.append(("a new memory is recalled at once",
                   any(i.id == item.id for i in recalled()), how))
    path = store.path_of(item.id)
    checks.append(("it is a readable Markdown file on disk",
                   bool(path and path.exists() and "Cult.fit" in path.read_text(encoding="utf-8")),
                   path.name if path else "no file"))

    twin, how = store.add(MemoryItem(
        cls="personal", title="Gym membership", tags=["gym"],
        body="Joined Cult.fit in Koramangala on a six-month plan; sessions Monday, "
             "Wednesday and Friday at 6:30am.", source_kind="manual"))
    checks.append(("a near-duplicate merges instead of piling up",
                   how == "merged" and twin.id == item.id, how))

    fresh = store.get(item.id)
    fresh.body = "Moved to Anytime Fitness in HSR Layout; sessions Tuesday and Thursday at 7pm."
    store.update(fresh)
    checks.append(("an edit is what gets recalled",
                   any("Anytime Fitness" in i.body for i in recalled()), ""))

    before = store.count()
    store.rebuild()
    checks.append(("the index rebuilds from the files alone",
                   store.count() == before and any(i.id == item.id for i in recalled()),
                   f"{before} items"))

    store.forget(item.id)
    checks.append(("a forgotten memory is gone from recall and from disk",
                   not any(i.id == item.id for i in recalled())
                   and not (path and path.exists()), ""))
    return checks


# ------------------------------------------------------------------ run

def last_result() -> Result:
    """The most recent saved E3 run, dated -- for the default eval pass and the
    app, which should not spend two minutes re-embedding to show a number."""
    runs = sorted(RECORDS.glob("e3-*.json")) if RECORDS.exists() else []
    if not runs:
        return unavailable("E3", TITLE, CLAIM,
                           "not run yet. It embeds two labelled personas and fits the "
                           "floors (about two minutes with Ollama): python -m app eval e3")
    data = json.loads(runs[-1].read_text(encoding="utf-8"))
    return Result(name="E3", title=TITLE, claim=CLAIM,
                  lines=[f"(saved run from {data.get('date', '?')} -- re-run: python -m app eval e3)",
                         ""] + list(data.get("lines", [])),
                  verdict=data.get("verdict", ""))


def run(progress=None) -> Result:
    if not embed.is_semantic():
        return unavailable("E3", TITLE, CLAIM,
                           f"the embedding backend is {embed.backend()!r}, the hashed "
                           "fallback, which cannot relate a paraphrase to its memory. "
                           "Start Ollama with nomic-embed-text.")
    shipped = shipped_params()
    dev = Persona(DEV, progress, "dev")
    test = Persona(HELDOUT, progress, "held-out")

    # C* on dev: fitted on four folds, scored on the fifth
    n = len(dev.queries)
    cv_rows: list[dict | None] = [None] * n
    folds = []
    for fold in range(FOLDS):
        train = [i for i in range(n) if i % FOLDS != fold]
        test_idx = [i for i in range(n) if i % FOLDS == fold]
        params = dev.fit(shipped, train)
        folds.append(params)
        for i, row in zip(test_idx, dev.score(params, test_idx)):
            cv_rows[i] = row
    dev.rows["C*"] = cv_rows                                  # type: ignore[assignment]
    fitted = dev.fit(shipped)                                 # all of dev
    test.rows["C*"] = test.score(fitted)

    life = lifecycle(dev.store, dev.pipeline)
    dstats = {c: summarise(r) for c, r in dev.rows.items()}
    tstats = {c: summarise(r) for c, r in test.rows.items()}
    order = ["A", "B", "C", "C*"]

    lines = [
        "PERCH-written benchmark, NOT LongMemEval/LoCoMo. Labels are ours: directional.",
        f"embedder {embed.backend()} ({config.EMBED_MODEL}); each persona in its own "
        "isolated store, never your memory",
        "",
        f"DEVELOPMENT persona -- {len(dev.data['items'])} memories, {n} questions. "
        "C* here is 5-fold cross-validated.",
    ] + table(dstats, order) + [
        "",
        f"HELD-OUT persona -- {len(test.data['items'])} memories, {len(test.queries)} "
        "questions. Never used for fitting.",
    ] + table(tstats, order) + [
        "",
        "    recall   share of needed memories admitted     hit   questions with >= 1 admitted",
        "    prec     admitted items that were needed or acceptable",
        "    abstain  questions needing nothing that drew nothing unrelated",
        "    leaks    questions where a HEALTH or PERSONAL memory got in uninvited",
        "",
        f"  ranker alone, before any gate: MRR {statistics.mean(dev.rr):.2f} dev / "
        f"{statistics.mean(test.rr):.2f} held-out; recall@{NAIVE_K} "
        f"{statistics.mean(dev.recall4):.2f} / {statistics.mean(test.recall4):.2f}",
        f"  gate latency (embed + route + rank + admit): median "
        f"{statistics.median(dev.gate_ms + test.gate_ms):.0f} ms, worst "
        f"{max(dev.gate_ms + test.gate_ms):.0f} ms",
        "",
        "  held-out by kind, C shipped -> C* (F1 / abstain / leaks)",
    ] + test.kinds(test.rows, "C", "C*") + [
        "",
        f"  {'':<12}{'shipped':>8}{'fitted':>8}   fold spread",
    ]
    for cls_name in mc.ORDER:
        spread = sorted(f["floors"][cls_name] for f in folds)
        lines.append(f"  {cls_name:<12}{shipped['floors'][cls_name]:>8.2f}"
                     f"{fitted['floors'][cls_name]:>8.2f}   {spread[0]:.2f}-{spread[-1]:.2f}")
    spread = sorted(f["alpha"] for f in folds)
    lines.append(f"  {'margin a':<12}{shipped['alpha']:>8.2f}{fitted['alpha']:>8.2f}   "
                 f"{spread[0]:.2f}-{spread[-1]:.2f}")

    lines += ["", "  memory lifecycle, real embedder:"]
    for label, ok, detail in life:
        lines.append(f"    {'PASS' if ok else 'FAIL'}  {label}" + (f"  ({detail})" if detail else ""))

    wrong = [(q, test.rows["C"][i]) for i, q in enumerate(test.queries)
             if test.rows["C"][i]["missed"] or test.rows["C"][i]["intrusions"]]
    lines += ["", f"  held-out, where C (shipped) went wrong: {len(wrong)} of {len(test.queries)}"]
    for q, r in wrong[:12]:
        bits = (["missed " + ",".join(r["missed"])] if r["missed"] else []) + \
               (["let in " + ",".join(r["intrusions"])] if r["intrusions"] else [])
        lines.append(f"    [{q['kind'][:5]}] {q['q'][:50]:<50} {'; '.join(bits)}")
    if len(wrong) > 12:
        lines.append(f"    ... and {len(wrong) - 12} more in the saved record")
    for p in (dev, test):
        if p.merged:
            lines.append(f"\n  note: {len(p.merged)} item(s) merged on write: {', '.join(p.merged)}")
        if p.mismatches:
            lines.append(f"\n  WARNING: {p.mismatches} question(s) where the replicated route "
                         "disagreed with the pipeline")

    c = tstats["C"]
    baseline = max(tstats["A"]["f1"], tstats["B"]["f1"]) + WIN_BY
    if c["leaks"]:
        head = "CONTRADICTS the privacy half on the held-out persona"
    elif c["f1"] >= baseline and c["abstain_ok"] >= tstats["B"]["abstain_ok"]:
        head = "SUPPORTS the claim on the held-out persona"
    elif c["f1"] >= baseline:
        head = "PARTLY SUPPORTS the claim on the held-out persona (abstains less than B)"
    else:
        head = "DOES NOT SUPPORT the claim on the held-out persona"
    verdict = (f"{head}: shipped F1 {c['f1']:.2f} vs naive top-k {tstats['A']['f1']:.2f} "
               f"and global threshold {tstats['B']['f1']:.2f}; abstention {c['abstain_ok']:.2f}; "
               f"private leaks {c['leaks']} (naive {tstats['A']['leaks']}). Lifecycle "
               f"{'all passed' if all(o for _, o, _ in life) else 'HAS FAILURES'}. "
               "Directional: labels written by the authors.")

    RECORDS.mkdir(parents=True, exist_ok=True)
    record = RECORDS / f"e3-{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    record.write_text(json.dumps({
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "embedder": embed.backend(), "shipped": shipped, "fitted_on_dev": fitted,
        "folds": folds, "dev": dstats, "heldout": tstats,
        "lifecycle": [{"check": l, "ok": o, "detail": d} for l, o, d in life],
        "dev_queries": dev.records, "heldout_queries": test.records,
        "lines": lines, "verdict": verdict,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    lines.append(f"\n  every question and what each config admitted: {record}")
    return Result(name="E3", title=TITLE, claim=CLAIM, lines=lines, verdict=verdict)
