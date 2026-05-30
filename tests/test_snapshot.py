"""Tests for `hexengine.snapshot` normalization used by state actions."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from hexengine.hexes.types import Hex
from hexengine.hooks.core import ENGINE_DEFAULT
from hexengine.snapshot import (
    assert_snapshot_json_serializable,
    attack_resolution_snapshot_fields,
    normalize_snapshot_mapping,
    normalize_snapshot_value,
)
from hexengine.state import GameState
from hexengine.state.title_extension import title_bucket
from hexengine.state.title_extension import title_bucket
from hexengine.state.actions import AddUnit, ApplyCombatEffects, Attack


def test_normalize_snapshot_value_primitives() -> None:
    assert normalize_snapshot_value(None) is None
    assert normalize_snapshot_value(True) is True
    assert normalize_snapshot_value(3) == 3
    assert normalize_snapshot_value("x") == "x"
    assert normalize_snapshot_value(1.5) == 1.5


def test_normalize_rejects_non_finite_float() -> None:
    with pytest.raises(ValueError, match="Non-finite"):
        normalize_snapshot_value(float("nan"))


def test_normalize_nested_dataclass() -> None:
    @dataclass(frozen=True)
    class Inner:
        roll: int
        note: str

    @dataclass(frozen=True)
    class Outer:
        inner: Inner
        flag: bool

    d = normalize_snapshot_value(Outer(Inner(4, "hit"), True))
    assert d == {"inner": {"roll": 4, "note": "hit"}, "flag": True}
    assert_snapshot_json_serializable(d)


def test_normalize_hex_dataclass_field() -> None:
    @dataclass(frozen=True)
    class Row:
        h: Hex

    d = normalize_snapshot_value(Row(Hex(1, 0, -1)))
    assert d == {"h": {"i": 1, "j": 0, "k": -1}}


def test_apply_combat_effects_expands_dataclass_last_combat_patch() -> None:
    @dataclass(frozen=True)
    class Patch:
        hexdemo_roll: int
        hexdemo_combat_result: str

    # ApplyCombatEffects normalizes nested dataclasses into JSON-safe dicts.
    a = ApplyCombatEffects({"last_combat_patch": Patch(3, "HIT")})
    assert a.effects == {"last_combat_patch": {"hexdemo_roll": 3, "hexdemo_combat_result": "HIT"}}


def test_attack_accepts_dataclass_rng_entry() -> None:
    @dataclass(frozen=True)
    class Rng:
        op: str
        roll: int

    st = GameState.create_empty(initial_faction="union", initial_phase="Combat")
    h = Hex(0, 0, 0)
    st = AddUnit("a", "inf", "union", h).apply(st)
    st = AddUnit("d", "inf", "confederate", Hex(1, 0, -1)).apply(st)

    atk = Attack(
        "combined",
        "a",
        "d",
        outcome="none",
        rng_entry=Rng("test", 7),
    )
    st2 = atk.apply(st)
    assert len(st2.rng_log) == 1
    assert st2.rng_log[0] == {"op": "test", "roll": 7}


def test_normalize_snapshot_mapping_root_must_be_mapping() -> None:
    with pytest.raises(TypeError, match="mapping root"):
        normalize_snapshot_mapping([])  # type: ignore[arg-type]


@dataclass(frozen=True)
class _EffectsDc:
    schema: int
    hexdemo_roll: int


def test_attack_resolution_snapshot_fields_dataclass_effects_root() -> None:
    r, e = attack_resolution_snapshot_fields(
        rng_entry=None,
        effects=_EffectsDc(1, 9),
    )
    assert r is None
    assert e == {"schema": 1, "hexdemo_roll": 9}
    assert_snapshot_json_serializable(e)


def test_attack_resolution_snapshot_fields_engine_default_as_none() -> None:
    r, e = attack_resolution_snapshot_fields(
        rng_entry=ENGINE_DEFAULT,
        effects=ENGINE_DEFAULT,
    )
    assert r is None and e is None
