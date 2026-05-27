"""Tests for title extension bucket helpers (engine boundary phase A/E)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from hexengine.state import GameState
from hexengine.state.title_extension import title_bucket
from hexengine.state.actions import PatchTitleBucket
from hexengine.state.action_manager import ActionManager
from hexengine.state.game_state import TurnState
from hexengine.state.snapshot import game_state_from_wire_dict, game_state_to_wire_dict
from hexengine.state.title_extension import (
    ENGINE_EXTENSION_KEY_PREFIX,
    is_engine_extension_key,
    title_bucket,
    with_title_bucket,
)
from hexengine.state.movement_arc import HEXENGINE_MOVEMENT_ARC_KEY


def test_is_engine_extension_key() -> None:
    assert is_engine_extension_key("hexengine_movement_arc")
    assert not is_engine_extension_key("hexdemo")


def test_title_bucket_missing_or_invalid() -> None:
    st = GameState.create_empty()
    assert title_bucket(st, None) == {}
    assert title_bucket(st, "") == {}
    assert title_bucket(st, "hexdemo") == {}


def test_title_bucket_reads_title_state() -> None:
    st = GameState.create_empty().with_title_state(
        {"combat_gate": "awaiting_advance", "n": 1},
        title_bucket_key="hexdemo",
    )
    hx = title_bucket(st, "hexdemo")
    assert hx["combat_gate"] == "awaiting_advance"
    assert hx["n"] == 1
    hx["combat_gate"] = "mutated"
    assert title_bucket(st, "hexdemo")["combat_gate"] == "awaiting_advance"


def test_with_title_bucket() -> None:
    st = GameState.create_empty().with_title_bucket_key("hexdemo")
    st2 = with_title_bucket(st, "hexdemo", {"a": 1})
    assert title_bucket(st2, "hexdemo") == {"a": 1}
    assert title_bucket(st, "hexdemo") == {}


def test_patch_title_bucket_action_undo() -> None:
    st = GameState.create_empty().with_title_state(
        {"combat_gate": "routine", "keep": True},
        title_bucket_key="hexdemo",
    )
    mgr = ActionManager(st)
    mgr.execute(PatchTitleBucket("hexdemo", {"combat_gate": "awaiting_advance"}, remove_keys=("keep",)))
    after = mgr.current_state
    hx = title_bucket(after, "hexdemo")
    assert hx["combat_gate"] == "awaiting_advance"
    assert "keep" not in hx
    mgr.undo()
    restored = title_bucket(mgr.current_state, "hexdemo")
    assert restored["combat_gate"] == "routine"
    assert restored["keep"] is True


def test_with_title_bucket_rejects_empty_key() -> None:
    with pytest.raises(ValueError):
        with_title_bucket(GameState.create_empty(), "", {})


def test_with_title_bucket_rejects_key_mismatch() -> None:
    st = GameState.create_empty().with_title_bucket_key("hexdemo")
    with pytest.raises(ValueError):
        with_title_bucket(st, "other", {})


def test_snapshot_wire_roundtrip_split_fields() -> None:
    st = GameState.create_empty().with_title_state(
        {"a": 1},
        title_bucket_key="hexdemo",
    ).with_engine_state({HEXENGINE_MOVEMENT_ARC_KEY: {"schema": 1}})
    wire = game_state_to_wire_dict(st)
    assert wire.get("title_state") == {"a": 1}
    assert wire.get("title_bucket_key") == "hexdemo"
    assert "extension" not in wire
    st2 = game_state_from_wire_dict(wire)
    assert title_bucket(st2, "hexdemo") == {"a": 1}
    assert st2.title_bucket_key == "hexdemo"


def test_engine_state_roundtrip() -> None:
    st = GameState.create_empty().with_engine_state(
        {HEXENGINE_MOVEMENT_ARC_KEY: {"gate": "awaiting_continue"}}
    )
    arc = st.engine_state[HEXENGINE_MOVEMENT_ARC_KEY]
    assert arc["gate"] == "awaiting_continue"
