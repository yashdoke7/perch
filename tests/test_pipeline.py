"""Tests for the parts of PERCH that carry the contribution.

Run:  python -m pytest tests -q

These do not need a model, a GPU or a network: the embedding backend is PINNED
to the hashed bag-of-words, which is enough to exercise routing, ranking,
admission and packing deterministically, and keeps the suite at a few seconds.

The pin matters. Left to probe, the suite quietly changed shape depending on
whether Ollama happened to be running -- 9 seconds offline, 134 seconds of HTTP
round trips when it was up, same assertions either way. The few tests that
genuinely need retrieval QUALITY opt in through the semantic_store fixture and
skip when no real embedder is reachable.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="perch-test-")
os.environ["PERCH_HOME"] = _TMP

# Pin the embedding backend for the bulk of the suite.
#
# Without this the suite silently changes shape depending on whether Ollama
# happens to be running: 9 seconds and no network when it is not, 134 seconds
# of HTTP round trips when it is. Same tests, same assertions, wildly
# different meaning -- and the docstring above claiming "no network required"
# quietly became false the moment a real embedder appeared.
#
# So: hashed by default, which is deterministic, offline and fast, and is all
# the plumbing tests need. The handful that genuinely test retrieval QUALITY
# opt in via the semantic_store fixture below.
os.environ.setdefault("PERCH_EMBED_BACKEND", "hashed")

import pytest  # noqa: E402

from app import config  # noqa: E402
from app.core import admission, packer, privacy, ranker, router  # noqa: E402
from app.memory import classes as mc  # noqa: E402
from app.memory import embed  # noqa: E402
from app.memory.schema import MemoryItem  # noqa: E402
from app.memory.store import MemoryStore  # noqa: E402


def _real_embedder_reachable() -> bool:
    """Is a real embedder available, regardless of what the suite pinned?"""
    import urllib.request
    from app import config as _config
    try:
        with urllib.request.urlopen(f"{_config.OLLAMA_URL}/api/tags", timeout=2):
            return True
    except Exception:
        return False


_HAS_REAL_EMBEDDER = _real_embedder_reachable()

# Tests that depend on retrieval QUALITY -- does a genuinely relevant item
# score above its floor? -- cannot run on the hashed stand-in, whose related
# and unrelated distributions overlap (see embed.is_semantic). They skip
# rather than fail when no embedder is reachable, so the suite is honest on a
# machine without Ollama instead of passing or failing on which happened to be
# running.
needs_semantic = pytest.mark.skipif(
    not _HAS_REAL_EMBEDDER,
    reason="needs a real embedder. Start Ollama (`ollama pull nomic-embed-text`) "
           "or set PERCH_API_BASE.",
)


@pytest.fixture(scope="module")
def store() -> MemoryStore:
    from app.seed import SEED
    s = MemoryStore(root=Path(_TMP) / "memory", db=Path(_TMP) / "index.sqlite3")
    for row in SEED:
        s.add(MemoryItem(source_kind="manual", **row))
    return s


@pytest.fixture(scope="module")
def _semantic_store():
    """The seed, embedded by a REAL model. Built once; costs HTTP round trips."""
    if not _HAS_REAL_EMBEDDER:
        pytest.skip("no real embedder")
    from app.seed import SEED
    previous = embed._backend
    embed._backend = "ollama"
    try:
        s = MemoryStore(root=Path(_TMP) / "sem-memory",
                        db=Path(_TMP) / "sem-index.sqlite3")
        for row in SEED:
            s.add(MemoryItem(source_kind="manual", **row))
    finally:
        embed._backend = previous
    return s


@pytest.fixture
def semantic_store(_semantic_store):
    """Switch the live backend to the real one for one test, then restore.

    Restoring matters: leaving it on ollama would make every later test in the
    session do HTTP, and would mismatch the hashed vectors in the main store --
    which index_health() would then correctly report as a stale index.
    """
    previous = embed._backend
    embed._backend = "ollama"
    try:
        yield _semantic_store
    finally:
        embed._backend = previous


# ------------------------------------------------------------------ the model

def test_six_classes_and_no_more():
    """The class set is closed. Adding a seventh is a design decision, not a
    convenience -- every class is another chance for the router to be wrong."""
    assert len(mc.CLASSES) == 6
    assert set(mc.ORDER) == set(mc.CLASSES)


def test_sensitive_classes_are_private_by_default():
    assert mc.is_private_class("health")
    assert mc.is_private_class("personal")
    assert not mc.is_private_class("project")


def test_identity_has_the_lowest_floor():
    """Identity is broad and cheap, so it should be admitted easily; health is
    specific, so a weak match there must not get through."""
    assert mc.floor_for("identity") < mc.floor_for("project")
    assert mc.floor_for("health") == max(c.floor for c in mc.CLASSES.values())


def test_item_roundtrips_through_markdown():
    item = MemoryItem(cls="project", title="A decision", body="Because of X.",
                      tags=["a", "b"], entities=["X"])
    parsed = MemoryItem.from_markdown(item.to_markdown())
    assert parsed is not None
    assert (parsed.cls, parsed.title, parsed.tags) == ("project", "A decision", ["a", "b"])
    assert "Because of X." in parsed.body


# ------------------------------------------------------------------ the store

def test_near_duplicates_merge_rather_than_accumulate(store):
    """The scale rule: a fact restated later must not become a second copy that
    then competes with itself at retrieval time."""
    before = store.count("career")
    again = MemoryItem(
        cls="career", title="What I am targeting after graduation",
        tags=["placement", "backend"],
        body="Targeting backend and applied-ML roles. Strongest in Python, "
             "comfortable with systems work and picking up Rust. Wants to stay "
             "in Pune or work remotely for the first role.")
    _, how = store.add(again)
    assert how == "merged"
    assert store.count("career") == before


def test_index_rebuilds_from_the_files(store):
    """The files are the truth; the index is derived."""
    total = store.count()
    assert store.rebuild() == total


# ----------------------------------------------------------------- the router

def test_transform_requests_ask_only_for_voice():
    intent = router.resolve("rewrite this more formally", selection="some text")
    assert intent.transform_only
    assert intent.eligible == ["identity"]


def test_health_cues_route_to_health():
    intent = router.resolve("what dosage did the doctor prescribe?")
    assert "health" in intent.eligible


def test_source_application_raises_project():
    intent = router.resolve("what is going on here?", selection="Traceback...",
                            source_app="Visual Studio Code", source_path="C:/x/main.py")
    assert "project" in intent.eligible


# -------------------------------------------------------------- ★ the gate

def test_a_class_below_its_floor_contributes_nothing(store):
    """The core claim: ranking is relative, injection is absolute.

    The store holds no health memory at all. The only item mentioning
    'medical' is an academic one about the campus. Nothing may be injected.
    """
    q = "what should I ask the doctor about my medication?"
    intent = router.resolve(q)
    cands = store.candidates(intent.eligible, embed.embed(q), config.OVERFETCH)
    result = admission.admit(ranker.rank(cands, q))

    assert result.abstained
    assert result.admitted == []
    assert result.classes_rejected, "the gate must record WHY it rejected"


def test_naive_top_k_would_have_leaked(store):
    """The counterfactual that makes the gate worth having.

    Without routing and without a floor, the same query pulls unrelated
    project and academic items -- the cross-domain leakage MemGate measures
    and OP-Bench penalises.
    """
    q = "what should I ask the doctor about my medication?"
    cands = store.candidates(list(mc.ORDER), embed.embed(q), config.OVERFETCH)
    naive = ranker.rank(cands, q)[:4]
    assert naive, "naive retrieval returns something"
    assert all(s.item.cls != "health" for s in naive), "and none of it is health"


@needs_semantic
def test_the_gate_still_admits_a_genuine_match(semantic_store):
    """A gate that never admits anything is not a gate, it is an off switch."""
    q = "why does the panel freeze when the model call is slow?"
    cands = semantic_store.candidates(["project", "identity"], embed.embed(q),
                                      config.OVERFETCH)
    result = admission.admit(ranker.rank(cands, q))
    assert not result.abstained
    assert any(s.item.cls == "project" for s in result.admitted)


def test_every_drop_carries_a_reason(store):
    """Auditability is the difference from a learned gate, so it is tested."""
    q = "what format does the panel expect for the base paper?"
    cands = store.candidates(list(mc.ORDER), embed.embed(q), config.OVERFETCH)
    result = admission.admit(ranker.rank(cands, q))
    for scored in result.admitted + result.dropped:
        assert scored.reason, f"{scored.item.id} has no reason recorded"


# ----------------------------------------------------------------- the packer

def test_budget_shrinks_with_the_context_window():
    """C1 in one assertion: the same memory layer, two very different models."""
    items = []
    big = packer.pack("q", "", items, context_window=128_000)
    small = packer.pack("q", "", items, context_window=8_192)
    assert big.budget > small.budget * 5


def test_items_enter_whole_or_not_at_all(store):
    """Half a project decision is worse than none -- it reads as a confident,
    incomplete fact."""
    q = "tell me about the project"
    cands = store.candidates(["project"], embed.embed(q), config.OVERFETCH)
    ranked = ranker.rank(cands, q)
    for s in ranked:
        s.admitted = True
    packed = packer.pack(q, "", ranked, context_window=1200)
    for scored in packed.included:
        assert scored.item.body.strip() in packed.prompt


def test_abstention_changes_the_system_prompt():
    packed = packer.pack("q", "", [], context_window=8192, abstained=True)
    assert "stored memory" in packed.system.lower()


# ---------------------------------------------------------------- the privacy

def test_toggle_wins_immediately():
    assert privacy.decide(True).private


def test_source_rule_matches_on_where_not_what():
    privacy.save_rules({"apps": ["keepass*"], "folders": [], "titles": ["*confidential*"]})
    assert privacy.decide(False, source_app="KeePassXC").private
    assert privacy.decide(False, source_title="Q3 CONFIDENTIAL draft").private
    assert not privacy.decide(False, source_app="notepad.exe").private


@needs_semantic
def test_admitting_private_class_forces_local(semantic_store):
    item = MemoryItem(cls="health", title="Current medication",
                      tags=["medication", "dosage"],
                      body="Prescribed 500 mg twice daily since June 2026.")
    semantic_store.add(item)
    q = "what is my current medication dosage?"
    cands = semantic_store.candidates(["health"], embed.embed(q), config.OVERFETCH)
    result = admission.admit(ranker.rank(cands, q))
    assert result.admitted
    assert result.forces_local, "health memory in the prompt must force local"
    semantic_store.forget(item.id)


def test_private_mode_never_selects_a_cloud_model():
    from app.models import registry
    assert registry.select(private=True).local


# ---------------------------------------------------------------- the hotkeys

def test_hotkey_dispatch_actually_fires_the_callback():
    """Regression: the message loop used to reach the callback by tuple index.

    When the binding tuple gained a fallback list and changed shape, that
    index went out of range, and the IndexError was swallowed by the loop's
    catch-all -- so hotkeys registered, Windows delivered them, and nothing
    happened. Nothing caught it because no test ever fired a binding.
    """
    from app.os_layer import hotkey

    fired = []
    listener = hotkey.HotkeyListener()
    hotkey_id = listener.bind(hotkey.MOD_CONTROL | hotkey.MOD_ALT, ord("J"),
                              lambda: fired.append("fired"), label="selection")

    assert listener.dispatch(hotkey_id) is True
    assert fired == ["fired"]


def test_hotkey_dispatch_survives_a_broken_handler():
    """A failing callback must not kill the listener thread."""
    from app.os_layer import hotkey

    def boom():
        raise RuntimeError("handler exploded")

    listener = hotkey.HotkeyListener()
    hotkey_id = listener.bind(hotkey.MOD_CONTROL, ord("K"), boom, label="plain")
    assert listener.dispatch(hotkey_id) is False        # reported, not raised
    assert listener.dispatch(9999) is False             # unknown id is safe


def test_synthetic_chords_wait_for_the_summoning_modifiers():
    """Regression: capture returned nothing because Alt was still held.

    PERCH is summoned by Ctrl+Alt+<key>, so when the callback runs the user
    is still physically holding Ctrl and Alt. Sending Ctrl+C on top of a held
    Alt delivers Ctrl+ALT+C to the target, which is not copy -- so the
    clipboard never changed, capture came back empty, and the model was asked
    about a selection it never received.
    """
    from app.os_layer import winapi

    # The invariant worth testing is that the guard is WIRED IN -- that is a
    # property of the code and is true on every machine, every run.
    import inspect
    assert "wait_for_modifier_release" in inspect.getsource(winapi._chord)

    # The rest reads real physical key state through GetAsyncKeyState, so it
    # is a fact about the machine at this instant, not about PERCH. Asserting
    # on it made this test fail roughly one run in three -- anyone holding
    # Shift while the suite ran turned the suite red for no reason, which
    # trains people to re-run until green and is worse than no test at all.
    # Skip instead: an intermittently-red test is a test that lies.
    if winapi.modifiers_held():
        pytest.skip("a modifier is physically held right now; nothing to assert about")
    assert winapi.wait_for_modifier_release() is True


def test_hotkey_combo_parsing_round_trips():
    from app import config

    mods, vk = config.parse_combo("ctrl+alt+shift+space")
    assert config.describe_combo(mods, vk) == "Ctrl+Alt+Shift+Space"
    assert config.parse_combo("ctrl+alt+j") == config.parse_combo("CTRL+ALT+J")


def test_private_mode_does_not_even_declare_network_tools():
    from app.tools import registry as toolreg
    offered = {s["function"]["name"] for s in toolreg.schemas(allow_network=False)}
    assert "web_search" not in offered
    assert "web_fetch" not in offered
    assert "memory_search" in offered


# ------------------------------------------------------- ★ write confirmation
#
# "Read is free, write asks" is architecture Part VI rule 1, and it was
# documented for some time while dispatch() ignored the confirm flag entirely.
# These tests exist so that cannot silently regress: the policy is only real
# if something fails when it is broken.

def test_a_confirming_tool_is_refused_when_nothing_can_ask(tmp_path):
    from app.tools import registry as toolreg
    target = tmp_path / "should-not-exist.txt"
    out = toolreg.dispatch("file_write", {"path": str(target), "content": "x"})
    assert out.startswith("refused")
    assert not target.exists(), "no callback must mean no write, not a silent write"


def test_declining_stops_the_write(tmp_path):
    from app.tools import registry as toolreg
    target = tmp_path / "declined.txt"
    out = toolreg.dispatch("file_write", {"path": str(target), "content": "x"},
                           on_confirm=lambda name, args: False)
    assert "declined" in out
    assert not target.exists()


def test_approving_lets_the_write_through(tmp_path):
    from app.tools import registry as toolreg
    target = Path(_TMP) / "approved.txt"          # inside PERCH_HOME, so _allowed
    seen: list[tuple[str, dict]] = []

    def approve(name: str, args: dict) -> bool:
        seen.append((name, args))
        return True

    toolreg.dispatch("file_write", {"path": str(target), "content": "hello"},
                     on_confirm=approve)
    assert target.read_text(encoding="utf-8") == "hello"
    assert seen[0][0] == "file_write", "the callback must see WHICH tool it is approving"


def test_a_broken_confirmation_callback_is_a_no(tmp_path):
    """A UI that raises must not read as approval."""
    from app.tools import registry as toolreg
    target = tmp_path / "broken.txt"

    def explode(name: str, args: dict) -> bool:
        raise RuntimeError("the panel was closed")

    out = toolreg.dispatch("file_write", {"path": str(target), "content": "x"},
                           on_confirm=explode)
    assert out.startswith("refused")
    assert not target.exists()


def test_reads_never_ask(store):
    """The other half of the rule: a read tool must not be gated."""
    from app.tools import registry as toolreg
    toolreg.bind_memory(store)
    asked = []
    out = toolreg.dispatch("memory_search", {"query": "who am I"},
                           on_confirm=lambda n, a: asked.append(n) or True)
    assert not asked, "memory_search is a read; gating it would train the user to click yes"
    assert not out.startswith("refused")


def test_memory_write_cannot_store_silently():
    """§3.4 rule 1: nothing is stored silently from ordinary chat."""
    from app.tools import registry as toolreg
    out = toolreg.dispatch("memory_write", {
        "cls": "identity", "title": "snuck in", "body": "should never be stored",
    })
    assert out.startswith("refused")


def test_running_code_asks_first():
    """run_python is not a sandbox, so the confirmation IS the containment."""
    from app.tools import registry as toolreg
    assert toolreg.TOOLS["run_python"].confirm, "run_python must never be free to call"
    out = toolreg.dispatch("run_python", {"code": "print(1)"})
    assert out.startswith("refused")


def test_the_prompt_says_what_will_actually_happen():
    from app.tools import registry as toolreg
    line = toolreg.describe_call("file_write", {"path": "C:/x.txt", "content": "y"})
    assert "file_write" in line and "C:/x.txt" in line


# ------------------------------------------------------ ★ stale index detection
#
# The failure these guard against was found in the live development store: 9 of
# 18 items had been embedded by Ollama (768-d) and 9 by the fallback (512-d).
# embed.cosine returns 0.0 on a length mismatch, so half the memory scored zero
# and was unretrievable -- which looks exactly like "nothing was relevant", and
# is therefore invisible. It also broke near-duplicate merging, leaving the same
# identity item stored twice.

def test_a_mismatched_vector_is_not_scored_as_merely_irrelevant(store):
    """A vector of the wrong length must be reported, not silently ranked last."""
    health = store.index_health(live_dim=999)
    assert health["stale"] == health["total"], (
        "every stored vector differs from a 999-d live backend, so all of them "
        "must be counted stale"
    )


def test_a_consistent_index_reports_no_staleness(store):
    health = store.index_health()
    assert health["stale"] == 0
    assert health["dims"] == {health["live_dim"]: health["total"]}


def test_cross_dimension_vectors_never_merge_by_accident():
    """cosine() is 0.0 across dimensions, which must not read as 'not a duplicate'
    on one path and 'perfectly unrelated' on another."""
    assert embed.cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


# ----------------------------------------------------------- ★ Phase 2: import
#
# §3.4's three write-side rules are what keep memory growth bounded, so each
# gets a test: nothing stored silently, extraction gated by review, and
# near-duplicates merging rather than accumulating.

FAKE_REPLY = """Here is what I found:

- title: PERCH is a Windows desktop AI agent
  tags: [perch, python, windows]
  entities: [PERCH]
  confidence: 0.9
  class: project
  body: |
    A personal AI agent triggered by a global hotkey, answering in a panel
    beside the user's work.
- title: Item whose body contains a dash line
  tags:
    - edge
    - case
  confidence: 0.35
  body: |
    The body has a bullet:
    - this line must not split the item
    and text after it.
- title: Malformed item with no body at all
  tags: [bad]
  confidence: 0.5
"""


@pytest.fixture
def fake_model():
    from app.models.registry import Model
    return Model(key="fake", provider="ollama", model_id="fake:1b",
                 context_window=8192, local=True, tools=True)


def _session(turns=None):
    from app.ingest.exports import Session
    return Session(platform="chatgpt", title="Project planning", created="",
                   turns=turns or [("user", "I am building PERCH."),
                                   ("assistant", "Tell me about retrieval.")])


def test_the_contract_parser_survives_realistic_model_output():
    """Preamble, block-style lists and in-body dashes are all normal output."""
    from app.ingest import extract
    props = extract.parse_contract(FAKE_REPLY, "project", platform="chatgpt")
    assert len(props) == 2, "the bodyless item must be dropped, the rest kept"
    assert props[0].item.tags == ["perch", "python", "windows"]
    assert props[1].item.tags == ["edge", "case"], "block-style lists must parse"
    assert "must not split the item" in props[1].item.body


def test_a_code_fence_does_not_defeat_the_parser():
    from app.ingest import extract
    fenced = "```yaml\n" + FAKE_REPLY.split("found:\n", 1)[1] + "\n```"
    assert len(extract.parse_contract(fenced, "project")) == 2


def test_one_bad_field_does_not_lose_the_batch():
    """The reason this is not PyYAML: a strict parse loses everything."""
    from app.ingest import extract
    broken = FAKE_REPLY.replace("  confidence: 0.9", "  confidence: not-a-number")
    props = extract.parse_contract(broken, "project")
    assert len(props) == 2
    assert props[0].confidence == 1.0, "an unparseable confidence falls back, not fatal"


def test_the_class_is_pinned_by_us_not_read_from_the_model():
    """The class IS the privacy boundary, so a model cannot choose it."""
    from app.ingest import extract
    reply = FAKE_REPLY.replace("class: project", "class: health")
    props = extract.parse_contract(reply, "project")
    assert all(p.item.cls == "project" for p in props)
    assert any("health" in w for w in props[0].warnings), "surface the disagreement"


def test_low_confidence_is_flagged_for_the_reviewer():
    from app.ingest import extract
    props = extract.parse_contract(FAKE_REPLY, "project")
    assert any("unsure" in w for w in props[1].warnings)


def test_extraction_refuses_rather_than_returning_nothing():
    """The stub cannot read a transcript, and pretending otherwise would be
    the same silent degradation the ablation and the index warning fixed."""
    from app.ingest import extract
    from app.models.registry import STUB
    with pytest.raises(extract.ExtractionUnavailable):
        extract.extract([_session()], "project", STUB)


def test_an_unreachable_model_is_not_an_empty_result(fake_model, monkeypatch):
    from app.ingest import extract
    from app.models import client as modelclient
    monkeypatch.setattr(modelclient, "complete",
                        lambda *a, **k: "(local model unreachable: refused)")
    with pytest.raises(extract.ExtractionUnavailable):
        extract.extract([_session()], "project", fake_model)


def test_long_sessions_split_at_turn_boundaries():
    """Cutting mid-turn yields items extracted from half a sentence."""
    from app.ingest import extract
    turns = [("user", "x" * 400), ("assistant", "y" * 400), ("user", "z" * 400)]
    chunks = extract._chunks(_session(turns), budget=900)
    assert len(chunks) > 1, "this must actually have split, or it proves nothing"
    for chunk in chunks:
        for line in chunk.splitlines():
            if line.strip():
                assert line.startswith(("USER:", "ASSISTANT:")), \
                    f"chunk boundary landed inside a turn: {line[:40]!r}"


def test_review_stores_nothing_without_an_explicit_yes(tmp_path, fake_model, monkeypatch):
    """§3.4 rule 1, and the reason a bare Enter means no."""
    from app.ingest import extract, review
    from app.models import client as modelclient
    monkeypatch.setattr(modelclient, "complete", lambda *a, **k: FAKE_REPLY)

    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    props = extract.extract([_session()], "project", fake_model)
    summary = review.review(props, s, ask=lambda _p: "", out=lambda *a: None)
    assert summary.accepted == 0
    assert s.count() == 0, "pressing Enter through a review must store nothing"


def test_review_stores_only_what_was_accepted(tmp_path, fake_model, monkeypatch):
    from app.ingest import extract, review
    from app.models import client as modelclient
    monkeypatch.setattr(modelclient, "complete", lambda *a, **k: FAKE_REPLY)

    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    props = extract.extract([_session()], "project", fake_model)
    answers = iter(["y", "n"])
    summary = review.review(props, s, ask=lambda _p: next(answers), out=lambda *a: None)
    assert (summary.accepted, summary.rejected) == (1, 1)
    assert s.count() == 1
    titles = [r[0] for r in s.db.execute("SELECT title FROM items").fetchall()]
    assert titles == ["PERCH is a Windows desktop AI agent"]


def test_quitting_review_leaves_the_rest_unstored(tmp_path, fake_model, monkeypatch):
    from app.ingest import extract, review
    from app.models import client as modelclient
    monkeypatch.setattr(modelclient, "complete", lambda *a, **k: FAKE_REPLY)

    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    props = extract.extract([_session()], "project", fake_model)
    summary = review.review(props, s, ask=lambda _p: "q", out=lambda *a: None)
    assert summary.quit_early and s.count() == 0


def test_editing_a_title_applies_before_it_is_stored(tmp_path, fake_model, monkeypatch):
    from app.ingest import extract, review
    from app.models import client as modelclient
    monkeypatch.setattr(modelclient, "complete", lambda *a, **k: FAKE_REPLY)

    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    props = extract.extract([_session()], "project", fake_model)
    answers = iter(["e", "A better title", "d"])
    review.review(props, s, ask=lambda _p: next(answers), out=lambda *a: None)
    titles = [r[0] for r in s.db.execute("SELECT title FROM items").fetchall()]
    assert titles == ["A better title"]


def test_a_reimported_fact_merges_instead_of_duplicating(tmp_path, fake_model, monkeypatch):
    """§3.4 rule 3 across two import runs -- the scale rule that stops a
    restated fact competing with itself at retrieval time."""
    from app.ingest import extract, review
    from app.models import client as modelclient
    monkeypatch.setattr(modelclient, "complete", lambda *a, **k: FAKE_REPLY)

    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    summary = None
    for _ in range(2):
        props = extract.extract([_session()], "project", fake_model)
        summary = review.review(props, s, ask=lambda _p: "a", out=lambda *a: None)
    assert summary.merged, "the second run must merge, not create"
    assert s.count() == 2, "two distinct facts, imported twice, stay two items"


def test_imported_items_carry_their_provenance():
    from app.ingest import extract
    props = extract.parse_contract(FAKE_REPLY, "project", platform="claude",
                                   session_title="Some old chat")
    assert props[0].item.source_kind == "import"
    assert props[0].item.source_platform == "claude"
    assert props[0].item.source_ref == "Some old chat"


def test_both_prompt_paths_share_one_contract():
    """Two prompt shapes are fine; two output formats would need two parsers."""
    from app.ingest import prompts
    pasted, driven = prompts.build("project"), prompts.build_system("project")
    assert prompts.CONTRACT in pasted and prompts.CONTRACT in driven
    assert "read everything above" in pasted
    assert "read everything above" not in driven


# ------------------------------------------- ★ Phase 3: one budget, two claimants
#
# C1's claim is not that memory has a budget -- everything has that -- it is
# that memory and TOOL RESULTS are charged against ONE allowance. That was
# documented in client.py's own docstring while the code appended result[:4000]
# and hoped: four tool steps overflowed an 8192-token local window by ~2300
# tokens, and the model then truncates from the far end, where the system
# prompt and memory live. These tests exist so it cannot silently regress.

def _scored(cls_name, title, body, score):
    from app.memory.schema import Scored
    return Scored(item=MemoryItem(cls=cls_name, title=title, body=body), score=score)


def _packed_with_memory(context_window=4096, n=4):
    items = [_scored("identity", "How I write",
                     "Plain English, British spelling, no padding.", 1.0)]
    items += [_scored("project", f"Decision {i}", "why this was chosen. " * 40,
                      0.9 - i * 0.1) for i in range(n)]
    return packer.pack("what changed?", "", items, context_window=context_window)


def test_a_tool_result_that_fits_evicts_nothing():
    from app.models import client
    p = _packed_with_memory(context_window=16_000)
    before = len(p.included)
    client._charge_tool_result(p, "a small result")
    assert len(p.included) == before
    assert p.used <= p.budget


def test_a_large_tool_result_is_paid_for_with_the_weakest_memory():
    from app.models import client
    p = _packed_with_memory()
    thrown = []
    client._charge_tool_result(p, "search result. " * 700, on_evict=thrown.append)
    evicted = [s for batch in thrown for s in batch]
    assert evicted, "a result far larger than headroom must cost something"
    assert p.used <= p.budget, f"budget blown: {p.used} > {p.budget}"
    # Lowest-ranked first: Decision 3 goes before Decision 0.
    order = [s.item.title for s in evicted]
    assert order[0] == "Decision 3", order


def test_identity_is_never_evicted_for_a_tool_result():
    """§4.5's fill order calls identity 'small, always'. A search result that
    costs the user their own voice is a bad trade at any size."""
    from app.models import client
    p = _packed_with_memory()
    thrown = []
    client._charge_tool_result(p, "search result. " * 900, on_evict=thrown.append)
    assert all(s.item.cls != "identity" for batch in thrown for s in batch)
    assert any(s.item.cls == "identity" for s in p.included), "identity must survive"
    assert "How I write" in p.prompt


def test_eviction_actually_leaves_the_prompt():
    """Freeing tokens in the ledger while still sending the text would make
    the whole accounting a lie."""
    from app.models import client
    p = _packed_with_memory()
    client._charge_tool_result(p, "search result. " * 700)
    for scored in p.evicted:
        assert scored.item.title not in p.prompt, f"{scored.item.title} still in the prompt"


def test_the_refreshed_prompt_reaches_the_model():
    """_refresh_prompt must update the user message the loop already built."""
    from app.models import client
    p = _packed_with_memory()
    messages = [{"role": "system", "content": p.system},
                {"role": "user", "content": p.prompt}]
    client._charge_tool_result(p, "search result. " * 700)
    client._refresh_prompt(messages, p)
    assert messages[1]["content"] == p.prompt
    assert "Decision 3" not in messages[1]["content"]


def test_when_nothing_can_be_evicted_the_result_is_truncated_not_appended():
    from app.models import client
    p = packer.pack("q", "", [], context_window=2048)
    p.used = p.budget - 400
    out = client._charge_tool_result(p, "x" * 50_000)
    assert len(out) < 50_000, "an oversized result must not be appended whole"
    assert p.used <= p.budget


def test_a_truncated_result_says_so():
    """A model reasoning from a fragment must know it is a fragment."""
    from app.models import client
    p = packer.pack("q", "", [], context_window=2048)
    p.used = p.budget - 400
    out = client._charge_tool_result(p, "x" * 50_000)
    assert "truncated" in out or "omitted" in out


def test_with_no_room_at_all_the_result_is_refused_rather_than_shredded():
    from app.models import client
    p = packer.pack("q", "", [], context_window=2048)
    p.used = p.budget - 5
    out = client._charge_tool_result(p, "x" * 50_000)
    assert "omitted" in out
    assert "do not invent" in out, "the model must be told not to fill the gap"


def test_four_tool_steps_no_longer_overflow_a_local_window():
    """The exact failure this phase fixes, at the size it actually happened."""
    from app.models import client
    p = _packed_with_memory(context_window=8192, n=8)
    for _ in range(client.MAX_TOOL_STEPS):
        client._charge_tool_result(p, "result. " * 500)
    assert p.used <= p.budget, f"still overflowing: {p.used} > {p.budget}"


def test_charging_without_a_ledger_still_works():
    """Callers that do not budget (tools off, direct use) must not crash."""
    from app.models import client
    assert client._charge_tool_result(None, "x" * 9000) == "x" * 4000


# ----------------------------------------------------- ★ Phase 3: route choice

def test_the_three_routes_are_the_ones_the_architecture_defines():
    from app.ui import panel as panelmod
    assert panelmod.ROUTES == ("auto", "local", "cloud")


def test_prefer_route_actually_selects(monkeypatch):
    """Request.prefer_route existed for a long time with nothing setting it."""
    from app.models import registry as reg
    monkeypatch.setattr(reg, "_ollama_up", lambda: True)
    monkeypatch.setattr(config, "API_BASE", "https://example.invalid")
    monkeypatch.setattr(config, "API_KEY", "k")
    assert reg.select(private=False, prefer="local").local
    assert not reg.select(private=False, prefer="cloud").local


def test_private_still_beats_an_explicit_cloud_preference(monkeypatch):
    """The one override that must never be honoured."""
    from app.models import registry as reg
    monkeypatch.setattr(reg, "_ollama_up", lambda: True)
    monkeypatch.setattr(config, "API_BASE", "https://example.invalid")
    monkeypatch.setattr(config, "API_KEY", "k")
    assert reg.select(private=True, prefer="cloud").local


def test_ask_parses_the_route_flag():
    """--route has to survive being mixed in with the question words."""
    import app.__main__ as m
    seen = {}

    class FakePipeline:
        def __init__(self, *a, **k): pass
        def run(self, req, **k):
            seen["route"] = req.prefer_route
            seen["private"] = req.private_toggle
            seen["q"] = req.question
            class T:
                def lines(self): return []
            return type("R", (), {"answer": "", "trace": T()})()

    original = m.Pipeline
    m.Pipeline = FakePipeline
    try:
        m.cmd_ask(["--route", "cloud", "why", "is", "this", "slow?"])
        assert seen == {"route": "cloud", "private": False, "q": "why is this slow?"}, seen
        m.cmd_ask(["--private", "--route=local", "hello"])
        assert seen["route"] == "local" and seen["private"] is True
    finally:
        m.Pipeline = original


# --------------------------------------------------- ★ Phase 5: the eval harness
#
# The property under test is not "the numbers are right" -- an experiment
# decides that. It is that the harness cannot QUIETLY not measure something.
# The gap between "we did not measure this" and "we measured this and it was
# fine" is the whole difference between an evaluation and a claim.

def test_all_seven_experiments_are_always_reported():
    from app.eval import harness
    names = set(harness.all_experiments())
    assert names == {"e1", "e2", "e3", "e4", "e5", "e6", "e7"}


def test_the_external_benchmarks_are_marked_not_run_with_a_reason():
    """E1 and E3 need datasets not vendored here. They must never look like
    passes, and E1 must not let OP-Bench's number be read as ours."""
    from app.eval import harness
    for result in (harness.e1_over_personalisation(), harness.e3_retrieval_quality()):
        assert not result.ran
        assert result.reason.strip(), f"{result.name} gives no reason"
        assert "NOT RUN" in result.render()
    e1 = harness.e1_over_personalisation()
    assert "not ours of PERCH" in e1.reason


def test_uia_coverage_says_why_it_cannot_be_simulated():
    from app.eval import harness
    e7 = harness.e7_uia_coverage()
    assert not e7.ran
    assert "mock" in e7.reason, "the point is that mocking it measures the mock"


def test_the_report_names_what_did_not_run():
    from app.eval import harness
    text = harness.report([harness.e1_over_personalisation(),
                           harness.e3_retrieval_quality(),
                           harness.e7_uia_coverage()])
    assert "0 of 3 experiments ran" in text
    for name in ("E1", "E3", "E7"):
        assert name in text
    assert "what it did not measure" in text


def test_a_crashing_experiment_is_reported_not_swallowed():
    """A crash must never be mistaken for 'did not apply'."""
    from app.eval import harness
    original = harness.all_experiments

    def boom():
        return {"e2": lambda: 1 / 0}

    harness.all_experiments = boom
    try:
        results = harness.run(["e2"])
    finally:
        harness.all_experiments = original
    assert len(results) == 1 and not results[0].ran
    assert "ZeroDivisionError" in results[0].reason


def test_e2_runs_offline_and_reaches_a_verdict(store):
    """C1 is a claim about assembly, so it is measurable with no model."""
    from app.eval import e2_budget
    result = e2_budget.run()
    assert result.ran
    assert result.verdict
    assert "CONFIRMED" in result.verdict
    body = "\n".join(result.lines)
    for window in ("4096", "8192", "128000"):
        assert window in body, f"{window} missing from the ablation"


def test_e2_reports_the_tool_contention_half(store):
    """The half that only became measurable once the ledger existed."""
    from app.eval import e2_budget
    body = "\n".join(e2_budget.run().lines)
    assert "append blindly" in body and "live ledger" in body
    assert "OVERFLOWS" in body, "config B must overflow somewhere, or C proves nothing"


def test_e4_refuses_to_score_on_the_fallback_embedder(store):
    """The harness inherits the ablation's own refusal rather than working
    around it -- one number, one source."""
    from app.eval import e4_admission
    from app.memory import embed
    result = e4_admission.run()
    if embed.is_semantic():
        assert result.ran
    else:
        assert not result.ran and "hashed" in result.reason


def test_e5_classifies_loopback_as_local_and_everything_else_as_remote():
    from app.eval import e5_privacy
    assert e5_privacy._is_local(("127.0.0.1", 11434))
    assert e5_privacy._is_local(("::1", 11434, 0, 0))
    assert not e5_privacy._is_local(("104.18.0.1", 443))
    assert not e5_privacy._is_local(("api.openai.com", 443))


def test_e5_recorder_actually_sees_a_connection():
    """If the instrumentation misses connections, a pass means nothing."""
    import socket
    from app.eval import e5_privacy
    with e5_privacy._Recorder() as rec:
        s = socket.socket()
        s.settimeout(0.05)
        try:
            s.connect(("127.0.0.1", 9))     # discard port; refusal is fine
        except OSError:
            pass
        finally:
            s.close()
    assert rec.attempts, "the recorder saw nothing, so it would pass anything"
    assert not rec.remote


def test_e5_restores_the_original_connect():
    """A permanently patched socket would poison every later test."""
    import socket
    from app.eval import e5_privacy
    before = socket.socket.connect
    with e5_privacy._Recorder():
        pass
    assert socket.socket.connect is before


def test_e5_passes_on_a_real_private_request(store):
    from app.eval import e5_privacy
    result = e5_privacy.run()
    assert result.ran
    assert "PASSED" in result.verdict, result.verdict
    assert "packet capture" in "\n".join(result.lines), \
        "the weaker-than-packet-capture caveat must survive"


# ------------------------------------------------- the probe E6 found was slow

def test_the_ollama_probe_is_cached():
    """It ran on EVERY request and cost ~4s when nothing was listening,
    because localhost resolves to both ::1 and 127.0.0.1."""
    from app.models import registry as reg
    reg.forget_probe()
    calls = {"n": 0}
    original = reg.urllib.request.urlopen

    def counting(*a, **k):
        calls["n"] += 1
        raise OSError("refused")

    reg.urllib.request.urlopen = counting
    try:
        for _ in range(10):
            reg._ollama_up()
    finally:
        reg.urllib.request.urlopen = original
        reg.forget_probe()
    assert calls["n"] == 1, f"probed {calls['n']} times; it must be cached"


def test_forget_probe_forces_a_fresh_check():
    """`models` must report what is true now, not what was true 30s ago."""
    from app.models import registry as reg
    reg.forget_probe()
    assert reg._probe is None


# --------------------------------------- ★ what a live run against Ollama found
#
# Everything below was written after running the system against a real embedder
# and a real 3B model for the first time. Each test corresponds to a defect that
# only a live run could surface -- unit tests with stubbed backends had passed
# over all of them.

def test_review_render_is_printable_on_a_windows_console():
    """It was not. U+2500 box-drawing is absent from cp1252, so print() raised
    UnicodeEncodeError and took `import` down at the moment it finally had
    proposals to show -- after a successful extraction."""
    from app.ingest import extract, review
    props = extract.parse_contract(FAKE_REPLY, "project", platform="chatgpt")
    text = review.render(props[0], 1, len(props))
    text.encode("cp1252")           # raises if any character is unencodable


def test_every_proposal_field_survives_a_cp1252_console():
    """The body is a model's text about arbitrary conversations, so it can
    contain anything. The header being ASCII is not enough on its own."""
    from app.ingest import extract, review
    reply = FAKE_REPLY.replace("A personal AI agent", "A personal AI agent — dash")
    props = extract.parse_contract(reply, "project")
    rendered = review.render(props[0], 1, 1)
    rendered.encode("cp1252", errors="replace")     # must not raise


def test_uncalibrated_confidence_is_detected():
    """qwen2.5:3b emitted `confidence: 1` for all four items it produced. It is
    filling in a required field, not estimating -- and the review screen's only
    automatic signal keys off that number."""
    from app.ingest import extract, review
    props = extract.parse_contract(FAKE_REPLY, "project")
    for p in props:
        p.item.confidence = 1.0
    assert review.uncalibrated(props)


def test_varied_confidence_is_not_flagged():
    from app.ingest import extract, review
    props = extract.parse_contract(FAKE_REPLY, "project")
    props[0].item.confidence = 0.9
    props[1].item.confidence = 0.4
    assert not review.uncalibrated(props)


def test_a_single_proposal_is_never_called_uncalibrated():
    """One sample says nothing about calibration."""
    from app.ingest import extract, review
    props = extract.parse_contract(FAKE_REPLY, "project")[:1]
    assert not review.uncalibrated(props)


def test_ollama_url_avoids_the_localhost_penalty():
    """Ollama binds IPv4 only. Resolving 'localhost' tries ::1 first and waits
    out a ~2s timeout on every call -- measured at 2051 ms against 42 ms for
    127.0.0.1, on every embedding and every generation."""
    assert "localhost" not in config.OLLAMA_URL, (
        "localhost costs ~2s per Ollama call on Windows; use 127.0.0.1")


# --------------------------------------------------------------- ★ deduplication

def _dupe_store(tmp_path, n=2):
    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    body = ("PERCH is a Windows desktop AI agent triggered by a global hotkey, "
            "answering in a panel beside the user's work.")
    for i in range(n):
        # allow_merge=False reproduces what the stale-index bug did: the write
        # path could not see the twin, so the duplicate was created.
        s.add(MemoryItem(cls="project", title="PERCH", body=body,
                         tags=["perch"]), allow_merge=False)
    return s


def test_duplicates_are_found(tmp_path):
    s = _dupe_store(tmp_path, n=3)
    assert s.count() == 3
    groups = s.find_duplicates()
    assert len(groups) == 1
    keeper, dupes = groups[0]
    assert len(dupes) == 2 and keeper not in dupes


def test_dedupe_is_a_dry_run_by_default(tmp_path):
    """It deletes memory files and the files are the truth -- there is no undo."""
    s = _dupe_store(tmp_path, n=3)
    s.dedupe()
    assert s.count() == 3, "a dry run must not change anything"


def test_dedupe_apply_collapses_the_group(tmp_path):
    s = _dupe_store(tmp_path, n=3)
    s.dedupe(apply=True)
    assert s.count() == 1
    assert not s.find_duplicates()


def test_dedupe_keeps_the_most_used_copy(tmp_path):
    """Use count is evidence the user actually relied on that copy."""
    s = _dupe_store(tmp_path, n=2)
    ids = [r[0] for r in s.db.execute("SELECT id FROM items").fetchall()]
    s.touch(ids[1])
    s.touch(ids[1])
    s.dedupe(apply=True)
    survivors = [r[0] for r in s.db.execute("SELECT id FROM items").fetchall()]
    assert survivors == [ids[1]]


def test_dedupe_unions_tags_rather_than_discarding_them(tmp_path):
    """A twin may carry a tag the keeper lacks; losing it is a silent downgrade."""
    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    body = "PERCH is a Windows desktop AI agent triggered by a global hotkey."
    s.add(MemoryItem(cls="project", title="PERCH", body=body, tags=["perch"]),
          allow_merge=False)
    s.add(MemoryItem(cls="project", title="PERCH", body=body, tags=["windows"]),
          allow_merge=False)
    s.dedupe(apply=True)
    remaining = s.get([r[0] for r in s.db.execute("SELECT id FROM items")][0])
    assert set(remaining.tags) == {"perch", "windows"}


def test_dedupe_leaves_genuinely_different_items_alone(tmp_path):
    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    s.add(MemoryItem(cls="project", title="A", body="Hotkeys use RegisterHotKey."))
    s.add(MemoryItem(cls="project", title="B", body="The packer fills a budget."))
    assert not s.find_duplicates()
    s.dedupe(apply=True)
    assert s.count() == 2


def test_dedupe_never_merges_across_classes(tmp_path):
    """A class is a privacy boundary; merging across one would move data."""
    s = MemoryStore(root=tmp_path / "m", db=tmp_path / "i.sqlite3")
    body = "Prescribed 500 mg twice daily since June 2026."
    s.add(MemoryItem(cls="health", title="Meds", body=body), allow_merge=False)
    s.add(MemoryItem(cls="personal", title="Meds", body=body), allow_merge=False)
    assert not s.find_duplicates(), "identical bodies in different classes are not duplicates"
