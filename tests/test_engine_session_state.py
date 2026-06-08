"""Tests for engine session-state bucket helpers."""

from __future__ import annotations

import pytest

from hexengine.state import GameState
from hexengine.state.action_manager import ActionManager
from hexengine.hooks.bucket import (
    ApplyBucketPatch,
    BucketPatch,
    clear_session_bucket,
)
from hexengine.state.movement_arc import HEXENGINE_MOVEMENT_ARC_KEY
from hexengine.state.snapshot import game_state_from_wire_dict, game_state_to_wire_dict
from hexengine.state.engine_session_state import (
    is_engine_extension_key,
    engine_read_session_state,
    engine_write_session_state,
)


def test_is_engine_extension_key() -> None:
    assert is_engine_extension_key("hexengine_movement_arc")
    assert not is_engine_extension_key("hexdemo")


def test_engine_read_session_state_missing_or_invalid() -> None:
    st = GameState.create_empty()
    assert engine_read_session_state(st, None) == {}
    assert engine_read_session_state(st, "") == {}
    assert engine_read_session_state(st, "hexdemo") == {}


def test_engine_read_session_state_reads_session_state() -> None:
    st = GameState.create_empty().with_session_state(
        {"marker": "a", "n": 1},
        session_state_key="hexdemo",
    )
    hx = engine_read_session_state(st, "hexdemo")
    assert hx["marker"] == "a"
    assert hx["n"] == 1
    hx["marker"] = "mutated"
    assert engine_read_session_state(st, "hexdemo")["marker"] == "a"


def test_engine_write_session_state() -> None:
    st = GameState.create_empty().with_session_state_key("hexdemo")
    st2 = engine_write_session_state(st, "hexdemo", {"a": 1})
    assert engine_read_session_state(st2, "hexdemo") == {"a": 1}
    assert engine_read_session_state(st, "hexdemo") == {}


def test_apply_bucket_patch_action_undo() -> None:
    st = GameState.create_empty().with_session_state(
        {"marker": "before", "keep": True},
        session_state_key="hexdemo",
    )
    mgr = ActionManager(st)
    mgr.execute(
        ApplyBucketPatch(
            "hexdemo",
            BucketPatch(values={"marker": "after"}, remove_keys=("keep",)),
        )
    )
    after = mgr.current_state
    hx = engine_read_session_state(after, "hexdemo")
    assert hx["marker"] == "after"
    assert "keep" not in hx
    mgr.undo()
    restored = engine_read_session_state(mgr.current_state, "hexdemo")
    assert restored["marker"] == "before"
    assert restored["keep"] is True


def test_engine_write_session_state_rejects_empty_key() -> None:
    with pytest.raises(ValueError):
        engine_write_session_state(GameState.create_empty(), "", {})


def test_engine_write_session_state_rejects_key_mismatch() -> None:
    st = GameState.create_empty().with_session_state_key("hexdemo")
    with pytest.raises(ValueError):
        engine_write_session_state(st, "other", {})


def test_snapshot_wire_roundtrip_split_fields() -> None:
    st = (
        GameState.create_empty()
        .with_session_state(
            {"a": 1},
            session_state_key="hexdemo",
        )
        .with_engine_state({HEXENGINE_MOVEMENT_ARC_KEY: {"schema": 1}})
    )
    wire = game_state_to_wire_dict(st)
    assert wire.get("session_state") == {"a": 1}
    assert wire.get("session_state_key") == "hexdemo"
    assert "extension" not in wire
    st2 = game_state_from_wire_dict(wire)
    assert engine_read_session_state(st2, "hexdemo") == {"a": 1}
    assert st2.session_state_key == "hexdemo"


def test_bucket_patch_remove_only() -> None:
    patch = BucketPatch.remove_only("a", "b")
    assert patch.values == {}
    assert patch.remove_keys == ("a", "b")


def test_clear_session_bucket() -> None:
    st = GameState.create_empty().with_session_state(
        {"keep": 1, "drop": 2},
        session_state_key="hexdemo",
    )
    assert clear_session_bucket(st, ()) == []
    assert clear_session_bucket(GameState.create_empty(), ("drop",)) == []
    actions = clear_session_bucket(st, ("drop", "missing"))
    assert len(actions) == 1
    mgr = ActionManager(st)
    mgr.execute(actions[0])
    hx = engine_read_session_state(mgr.current_state, "hexdemo")
    assert hx == {"keep": 1}


def test_engine_state_roundtrip() -> None:
    st = GameState.create_empty().with_engine_state(
        {HEXENGINE_MOVEMENT_ARC_KEY: {"gate": "awaiting_continue"}}
    )
    arc = st.engine_state[HEXENGINE_MOVEMENT_ARC_KEY]
    assert arc["gate"] == "awaiting_continue"
