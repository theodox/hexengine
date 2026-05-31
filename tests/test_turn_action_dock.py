"""Turn action dock hook and StateUpdate wiring."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
SRC = str(REPO_ROOT / "src")
for p in (GAMES, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexengine.hooks.ui import TurnActionDockContext
from hexengine.hooks.ui_turn_action_dock import default_turn_action_dock_for_viewer
from hexengine.server.game_server import GameServer
from hexengine.state import GameState


def _hexdemo_server() -> GameServer:
    from hexdemo.game_config import (
        HexdemoGameDefinition,
        default_match_config,
        game_definition_from_config,
    )
    from hexengine.scenarios import load_scenario
    from hexengine.scenarios.loader import scenario_to_initial_state

    scenario_path = REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
    scenario_data = load_scenario(scenario_path)
    gd = HexdemoGameDefinition(game_definition_from_config(default_match_config()))
    first = {"faction": "union", "phase": "Combat", "max_actions": 4}
    st = scenario_to_initial_state(
        scenario_data,
        initial_faction=first["faction"],
        initial_phase=first["phase"],
        phase_actions_remaining=int(first["max_actions"]),
        schedule_index=0,
        game_definition=gd,
    )
    return GameServer(
        initial_state=st,
        game_definition=gd,
        pack_id="hexdemo",
        pack_root=REPO_ROOT / "games" / "hexdemo",
    )


def test_hexdemo_build_hooks_wires_turn_action_dock() -> None:
    from games.hexdemo.hooks import build_hooks

    th = build_hooks()
    assert th.ui.turn_action_dock_for_viewer is not None
    assert th.ui.interaction_panels_for_viewer is None


def test_catalog_default_includes_end_phase_for_turn_owner() -> None:
    st = GameState.create_empty()
    ctx = TurnActionDockContext(
        state=st,
        viewer_faction="union",
        extension_key="hexdemo",
        shell_ui={"advance_turn_button_label": "End Phase"},
        schedule_index=0,
        current_faction="union",
        current_phase="Move",
        phase_actions_remaining=2,
        viewer_is_turn_owner=True,
        client_contract_features=frozenset(),
    )
    panels = default_turn_action_dock_for_viewer(ctx)
    assert len(panels) == 1
    panel = panels[0]
    assert panel["id"] == "turn_actions"
    ids = [a["id"] for a in panel["actions"]]
    assert "end_phase" in ids
    end = next(a for a in panel["actions"] if a["id"] == "end_phase")
    assert end["action_type"] == "NextPhase"
    assert end["enabled"] is True


def test_hexdemo_state_update_uses_turn_action_dock_panels() -> None:
    from hexengine.server.protocol import PlayerInfo

    server = _hexdemo_server()
    server.players["p_union"] = PlayerInfo(
        player_id="p_union",
        player_name="Union",
        faction="union",
        connected=True,
    )
    panels = server._interaction_panels_for_player_id("p_union")
    assert panels is not None
    assert any(p.get("id") == "turn_actions" for p in panels)


def test_hexdemo_combat_phase_enables_end_phase_without_gate() -> None:
    from games.hexdemo.hooks.turn_action_dock import turn_action_dock_for_viewer
    from hexengine.arcs.segment_wire import project_current_segment
    from hexengine.state.game_state import TurnState

    st = GameState.create_empty()
    turn = TurnState(
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=2,
        turn_number=st.turn.turn_number,
        schedule_index=1,
        global_tick=st.turn.global_tick,
    )
    st = GameState(board=st.board, turn=turn, title_state={}, title_bucket_key="hexdemo", rng_log=())
    from hexengine.server import GameServer
    from games.hexdemo.game_config import game_definition_from_config, default_match_config

    server = GameServer(st, game_definition=game_definition_from_config(default_match_config()))
    seg = project_current_segment(server, server.game_state, viewer_faction="union")
    ctx = TurnActionDockContext(
        state=server.game_state,
        viewer_faction="union",
        extension_key="hexdemo",
        shell_ui={},
        schedule_index=1,
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=2,
        viewer_is_turn_owner=True,
        client_contract_features=frozenset(),
        current_segment=seg,
    )
    panels = turn_action_dock_for_viewer(ctx)
    assert panels[0]["dock_arc"] == "attack_ready"
    end = next(a for a in panels[0]["actions"] if a["id"] == "end_phase")
    assert end["enabled"] is True


def test_hexdemo_retreat_gate_shows_for_non_turn_owner() -> None:
    from games.hexdemo.hooks.turn_action_dock import turn_action_dock_for_viewer
    from hexengine.arcs import ArcCursor, SetArcCursor
    from hexengine.hexes.types import Hex
    from hexengine.server.arcs import lookup_arc_spec
    from hexengine.arcs.segment_wire import project_current_segment
    from hexengine.state.action_manager import ActionManager
    from hexengine.state.game_state import BoardState, TurnState, UnitState

    from games.hexdemo import combat_arc
    from games.hexdemo.hooks import build_hooks

    st = GameState.create_empty()
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
        title_state={
            "combat_gate": "awaiting_retreat_or_disrupt",
            "retreat_obligations": {"u_def": 1},
        },
        title_bucket_key="hexdemo",
        rng_log=(),
    )
    am = ActionManager(st)
    am.execute(
        SetArcCursor(
            ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_RETREAT_OR_DISRUPT_GATE)
        )
    )
    st = am.current_state

    class _Host:
        hooks = build_hooks()

        def lookup_arc_spec(self, arc_id: str):
            return lookup_arc_spec(self, arc_id)

    seg = project_current_segment(_Host(), st, viewer_faction="confederate")
    ctx = TurnActionDockContext(
        state=st,
        viewer_faction="confederate",
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
    panels = turn_action_dock_for_viewer(ctx)
    assert len(panels) == 1
    assert panels[0]["dock_arc"] == "retreat_gate"
    ids = {a["id"] for a in panels[0]["actions"]}
    assert "combat_disrupt_instead" in ids


def test_hexdemo_retreat_obligation_shows_dock_for_non_turn_owner() -> None:
    from games.hexdemo.hooks.turn_action_dock import turn_action_dock_for_viewer
    from hexengine.arcs import ArcCursor, SetArcCursor
    from hexengine.hexes.types import Hex
    from hexengine.server.arcs import lookup_arc_spec
    from hexengine.arcs.segment_wire import project_current_segment
    from hexengine.state.action_manager import ActionManager
    from hexengine.state.game_state import BoardState, TurnState, UnitState

    from games.hexdemo import combat_arc
    from games.hexdemo.hooks import build_hooks

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
        title_state={
            "combat_gate": "awaiting_retreat",
            "retreat_obligations": {"u_def": 1},
        },
        title_bucket_key="hexdemo",
        rng_log=(),
    )
    am = ActionManager(st)
    am.execute(
        SetArcCursor(
            ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_RETREAT_GATE)
        )
    )
    st = am.current_state

    class _Host:
        hooks = build_hooks()

        def lookup_arc_spec(self, arc_id: str):
            return lookup_arc_spec(self, arc_id)

    seg = project_current_segment(_Host(), st, viewer_faction="confederate")
    ctx = TurnActionDockContext(
        state=st,
        viewer_faction="confederate",
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
    panels = turn_action_dock_for_viewer(ctx)
    assert len(panels) == 1
    assert panels[0]["dock_arc"] == "retreat_gate"
    assert "end_phase" in {a["id"] for a in panels[0]["actions"]}


def test_hexdemo_advance_gate_disables_end_phase() -> None:
    from games.hexdemo.hooks.turn_action_dock import turn_action_dock_for_viewer
    from hexengine.arcs import ArcCursor, SetArcCursor
    from hexengine.hexes.types import Hex
    from hexengine.server.arcs import lookup_arc_spec
    from hexengine.arcs.segment_wire import project_current_segment
    from hexengine.state.action_manager import ActionManager
    from hexengine.state.game_state import BoardState, TurnState, UnitState

    from games.hexdemo import combat_arc
    from games.hexdemo.hooks import build_hooks

    board = BoardState(
        units={
            "u1": UnitState(
                unit_id="u1",
                unit_type="inf",
                faction="union",
                position=Hex(0, 0, 0),
                health=10,
                active=True,
            )
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
        title_state={
            "combat_gate": "awaiting_advance",
            "advance": {"faction": "union"},
        },
        title_bucket_key="hexdemo",
        rng_log=(),
    )
    am = ActionManager(st)
    am.execute(
        SetArcCursor(
            ArcCursor(arc_id="combat", segment_id=combat_arc.SEG_ADVANCE_GATE)
        )
    )
    st = am.current_state

    class _Host:
        hooks = build_hooks()

        def lookup_arc_spec(self, arc_id: str):
            return lookup_arc_spec(self, arc_id)

    seg = project_current_segment(_Host(), st, viewer_faction="union")
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
    panels = turn_action_dock_for_viewer(ctx)
    actions = panels[0]["actions"]
    ids = [a["id"] for a in actions]
    assert "combat_advance" in ids
    assert "end_phase" in ids
    end = next(a for a in actions if a["id"] == "end_phase")
    assert end["enabled"] is False
