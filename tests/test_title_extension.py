"""Tests for title extension bucket helpers (engine boundary phase A)."""

from __future__ import annotations

import dataclasses

import pytest

from hexengine.state import GameState
from hexengine.state.actions import PatchTitleBucket
from hexengine.state.action_manager import ActionManager
from hexengine.state.game_state import TurnState
from hexengine.state.title_extension import (
    ENGINE_EXTENSION_KEY_PREFIX,
    is_engine_extension_key,
    title_bucket,
    with_title_bucket,
)


def test_is_engine_extension_key() -> None:
    assert is_engine_extension_key("hexengine_movement_arc")
    assert not is_engine_extension_key("hexdemo")


def test_title_bucket_missing_or_invalid() -> None:
    st = GameState.create_empty()
    assert title_bucket(st, None) == {}
    assert title_bucket(st, "") == {}
    assert title_bucket(st, "hexdemo") == {}


def test_title_bucket_reads_dict() -> None:
    st = GameState.create_empty().with_extension(
        {"hexdemo": {"combat_gate": "awaiting_advance", "n": 1}}
    )
    hx = title_bucket(st, "hexdemo")
    assert hx["combat_gate"] == "awaiting_advance"
    assert hx["n"] == 1
    hx["combat_gate"] = "mutated"
    assert title_bucket(st, "hexdemo")["combat_gate"] == "awaiting_advance"


def test_with_title_bucket() -> None:
    st = GameState.create_empty()
    st2 = with_title_bucket(st, "hexdemo", {"a": 1})
    assert title_bucket(st2, "hexdemo") == {"a": 1}
    assert title_bucket(st, "hexdemo") == {}


def test_patch_title_bucket_action_undo() -> None:
    st = GameState.create_empty().with_extension(
        {"hexdemo": {"combat_gate": "routine", "keep": True}}
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
