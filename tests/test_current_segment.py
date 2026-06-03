"""Current segment wire projection and affordances (composable arcs, Phase 5)."""

from __future__ import annotations

from hexengine.arcs import ArcCursor, SetArcCursor, read_arc_cursor
from hexengine.arcs.segment_wire import (
    action_rows_from_segment,
    project_current_segment,
    segment_allows_action,
    segment_blocks_routine_phase_advance,
)
from hexengine.hexes.types import Hex
from hexengine.hooks.ui import TurnActionDockContext
from hexengine.server import GameServer
from hexengine.state import ActionManager, GameState
from hexengine.state.game_state import BoardState, TurnState, UnitState

from games.hexdemo import combat_arc, combat_transitions
from games.hexdemo.hooks import build_hooks


def _state_on_combat_segment(
    gate_segment: str,
    *,
    viewer_faction: str,
    obligations: dict[str, int] | None = None,
    advance: dict | None = None,
) -> GameState:
    unit = UnitState(
        unit_id="u1", unit_type="inf", faction=viewer_faction, position=Hex(0, 0, 0)
    )
    st = GameState.create_empty()
    st = st.with_board(st.board.with_unit(unit))
    st = st.with_turn(
        TurnState(
            current_faction=viewer_faction,
            current_phase="Combat",
            phase_actions_remaining=2,
            turn_number=1,
            schedule_index=0,
            global_tick=0,
        )
    )
    bucket: dict = {"combat_gate": gate_segment.replace("_gate", "").replace("SEG_", "")}
    if obligations is not None:
        bucket["retreat_obligations"] = obligations
    if advance is not None:
        bucket["advance"] = advance
    st = st.with_title_state(bucket, title_bucket_key="hexdemo")
    am = ActionManager(st)
    am.execute(
        SetArcCursor(ArcCursor(arc_id="combat", segment_id=gate_segment))
    )
    return am.current_state


class _ProjectHost:
    hooks = build_hooks()

    def lookup_arc_spec(self, arc_id: str):
        from hexengine.server.arcs import lookup_arc_spec

        return lookup_arc_spec(self, arc_id)


def test_project_routine_combat_segment() -> None:
    from hexengine.server.arcs import begin_routine_slot

    gd = __import__(
        "games.hexdemo.game_config",
        fromlist=["game_definition_from_config", "default_match_config"],
    )
    gd_fn = gd.game_definition_from_config(gd.default_match_config())
    st = GameState.create_empty().with_turn(
        TurnState("union", "Combat", 2, 1, 1, 0)
    )
    server = GameServer(st, game_definition=gd_fn)
    seg = project_current_segment(server, server.game_state, viewer_faction="union")
    assert seg is not None
    assert seg["arc_id"] == "union_combat"
    assert "Attack" in seg["allowed_actions"]
    assert seg["action_locus"]["Attack"] == "client_draft"
    assert seg.get("presentation_id") == "attack_ready"
    assert seg.get("interaction_mode") == "attack_plan"


def test_project_retreat_gate_owner_and_actions() -> None:
    st = _state_on_combat_segment(
        combat_arc.SEG_RETREAT_OR_DISRUPT_GATE,
        viewer_faction="confederate",
        obligations={"u_def": 1},
    )
    st = st.with_board(
        BoardState(
            units={
                "u_def": UnitState(
                    "u_def", "inf", "confederate", Hex(0, 0, 0), active=True
                )
            }
        )
    )
    host = _ProjectHost()
    seg = project_current_segment(host, st, viewer_faction="confederate")
    assert seg is not None
    assert seg["owner"] == "confederate"
    assert "CombatDisruptInsteadOfRetreat" in seg["allowed_actions"]
    assert "NextPhase" not in seg["allowed_actions"]
    assert seg.get("presentation_id") == "retreat_gate"
    assert seg.get("interaction_mode") == "retreat_path"


def test_advance_gate_blocks_next_phase() -> None:
    st = _state_on_combat_segment(
        combat_arc.SEG_ADVANCE_GATE,
        viewer_faction="union",
        advance={"faction": "union"},
    )
    host = _ProjectHost()
    assert segment_blocks_routine_phase_advance(host, st, viewer_faction="union") is True


def test_action_rows_from_advance_segment() -> None:
    st = _state_on_combat_segment(
        combat_arc.SEG_ADVANCE_GATE,
        viewer_faction="union",
        advance={"faction": "union"},
    )
    host = _ProjectHost()
    seg = project_current_segment(host, st, viewer_faction="union")
    rows = action_rows_from_segment(seg, {})
    ids = {r["id"] for r in rows}
    assert "combat_advance" in ids
    assert "combat_decline_advance" in ids


def test_dock_end_phase_follows_segment() -> None:
    from games.hexdemo.hooks.turn_action_dock import turn_action_dock_for_viewer

    st = _state_on_combat_segment(
        combat_arc.SEG_ADVANCE_GATE,
        viewer_faction="union",
        advance={"faction": "union"},
    )
    host = _ProjectHost()
    seg = project_current_segment(host, st, viewer_faction="union")
    ctx = TurnActionDockContext(
        state=st,
        viewer_faction="union",
        extension_key="hexdemo",
        shell_ui={},
        schedule_index=0,
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=1,
        viewer_is_turn_owner=True,
        client_contract_features=frozenset(),
        current_segment=seg,
    )
    from hexengine.hooks.internal.ui_wire import turn_action_dock_to_wire

    panels = turn_action_dock_to_wire(turn_action_dock_for_viewer(ctx))
    end = next(a for a in panels[0]["actions"] if a["id"] == "end_phase")
    assert end["enabled"] is False
