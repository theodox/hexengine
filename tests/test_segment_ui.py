"""Hexdemo segment presentation registry."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
if GAMES not in sys.path:
    sys.path.insert(0, GAMES)

from hexdemo.combat_transitions import (
    GATE_AWAITING_ADVANCE,
    GATE_AWAITING_RETREAT,
    GATE_AWAITING_RETREAT_OR_DISRUPT,
)
from hexdemo.presentation.dock import dock_headline
from hexdemo.segment_ui import (
    PRESENTATION_BY_SEGMENT_KIND,
    Primitive,
    resolve_presentation_id,
    segment_presentation,
)


def test_registry_covers_combat_gate_kinds() -> None:
    assert GATE_AWAITING_RETREAT in PRESENTATION_BY_SEGMENT_KIND
    assert GATE_AWAITING_RETREAT_OR_DISRUPT in PRESENTATION_BY_SEGMENT_KIND
    assert GATE_AWAITING_ADVANCE in PRESENTATION_BY_SEGMENT_KIND
    row = segment_presentation({"kind": GATE_AWAITING_RETREAT, "schema": 1})
    assert row is not None
    assert row.presentation_id == "retreat_gate"
    assert row.interaction_mode == "retreat_path"
    assert row.primitive == Primitive.SELECT


def test_resolve_presentation_id_combat_phase_slot() -> None:
    pid = resolve_presentation_id(
        {"kind": "combat", "allowed_actions": ["Attack", "NextPhase"]},
        viewer_may_act=True,
        current_phase="Combat",
    )
    assert pid == "attack_ready"


def test_resolve_presentation_id_fallback_hidden() -> None:
    pid = resolve_presentation_id(
        None,
        viewer_may_act=False,
        current_phase="Move",
    )
    assert pid == "hidden"


def test_dock_headline_from_presentation_id() -> None:
    assert (
        dock_headline(
            {"dock_retreat_gate_headline": "Hold for retreat"}, "retreat_gate"
        )
        == "Hold for retreat"
    )
    assert dock_headline({}, "hidden") == ""
