"""Tests for the parts of PERCH that carry the contribution.

Run:  python -m pytest tests -q

These do not need a model, a GPU or a network. The embedding backend falls
back to a hashed bag-of-words, which is enough to exercise routing, ranking,
admission and packing deterministically.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_TMP = tempfile.mkdtemp(prefix="perch-test-")
os.environ["PERCH_HOME"] = _TMP

import pytest  # noqa: E402

from app import config  # noqa: E402
from app.core import admission, packer, privacy, ranker, router  # noqa: E402
from app.memory import classes as mc  # noqa: E402
from app.memory import embed  # noqa: E402
from app.memory.schema import MemoryItem  # noqa: E402
from app.memory.store import MemoryStore  # noqa: E402


@pytest.fixture(scope="module")
def store() -> MemoryStore:
    from app.seed import SEED
    s = MemoryStore(root=Path(_TMP) / "memory", db=Path(_TMP) / "index.sqlite3")
    for row in SEED:
        s.add(MemoryItem(source_kind="manual", **row))
    return s


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


def test_the_gate_still_admits_a_genuine_match(store):
    """A gate that never admits anything is not a gate, it is an off switch."""
    q = "why does the panel freeze when the model call is slow?"
    cands = store.candidates(["project", "identity"], embed.embed(q), config.OVERFETCH)
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


def test_admitting_private_class_forces_local(store):
    item = MemoryItem(cls="health", title="Current medication",
                      tags=["medication", "dosage"],
                      body="Prescribed 500 mg twice daily since June 2026.")
    store.add(item)
    q = "what is my current medication dosage?"
    cands = store.candidates(["health"], embed.embed(q), config.OVERFETCH)
    result = admission.admit(ranker.rank(cands, q))
    assert result.admitted
    assert result.forces_local, "health memory in the prompt must force local"
    store.forget(item.id)


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

    assert winapi.modifiers_held() == [], "test env should have no keys held"
    assert winapi.wait_for_modifier_release() is True
    # The guard must be wired into the chord helper, not just available.
    import inspect
    assert "wait_for_modifier_release" in inspect.getsource(winapi._chord)


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
