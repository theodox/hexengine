"""Hexdemo arc_segment projection helpers."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
SRC = str(REPO_ROOT / "src")
for p in (GAMES, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from games.hexdemo.combat import arc as combat_arc
from games.hexdemo.arcs import segment as arc_segment

from hexengine.arcs import ArcCursor, SetArcCursor
from hexengine.hexes.types import Hex
from hexengine.state import GameState
from hexengine.state.action_manager import ActionManager
from hexengine.state.game_state import BoardState, TurnState, UnitState


def _retreat_gate_state() -> GameState:
    board = BoardState(
        units={
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="inf",
                faction="confederate",
                position=Hex(0, 0, 0),
                health=10,
                active=True,
            ),
        }
    )
    turn = TurnState(
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=1,
        turn_number=1,
        schedule_index=0,
        global_tick=0,
    )
    st = GameState(
        board=board,
        turn=turn,
        session_state={
            "retreat_obligations": {"u_def": 1},
        },
        session_state_key="hexdemo",
        rng_log=(),
    )
    am = ActionManager(st)
    am.execute(
        SetArcCursor(ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_RETREAT_GATE))
    )
    return am.current_state


def test_project_segment_for_faction_retreat_gate_kind() -> None:
    st = _retreat_gate_state()
    seg = arc_segment.project_segment_for_faction(st, "confederate")
    assert seg is not None
    assert seg.get("ui_mode") == "awaiting_retreat"
    assert seg.get("presentation_id") == "retreat_gate"


def test_segment_denies_attack_during_retreat_gate() -> None:
    st = _retreat_gate_state()
    assert arc_segment.segment_denies_action(st, "union", "Attack") is True


def test_phase_advance_blocked_during_retreat_gate() -> None:
    st = _retreat_gate_state()
    assert arc_segment.phase_advance_blocked(st) is True
