"""Authoritative drag preview (Track C) — server preview matches move validation."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
if GAMES not in sys.path:
    sys.path.insert(0, GAMES)

from hexengine.hexes.types import Hex
from hexengine.server.game_server import GameServer
from hexengine.server.preview import compute_unit_drag_preview
from hexengine.state.logic import is_valid_move


def _hexdemo_server() -> GameServer:
    from games.hexdemo.game_config import (
        default_match_config,
        game_definition_from_config,
    )

    from hexengine.scenarios import load_scenario
    from hexengine.scenarios.loader import scenario_to_initial_state

    scenario_path = (
        REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
    )
    scenario_data = load_scenario(scenario_path)
    gd = game_definition_from_config(default_match_config())
    first = {"faction": "union", "phase": "Move", "max_actions": 4}
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
        map_display=scenario_data.map_display.to_wire_dict(),
        global_styles=scenario_data.global_styles.to_wire_dict(),
        unit_graphics=scenario_data.unit_graphics_to_wire_dict(),
        marker_graphics=scenario_data.marker_graphics_to_wire_dict(),
        markers=scenario_data.markers_to_wire_list(),
        game_definition=gd,
    )


def test_turn_rules_advertises_server_drag_previews() -> None:
    server = _hexdemo_server()
    tr = server._turn_rules_wire()
    feats = tr.get("client_contract", {}).get("features", [])
    assert "server_drag_previews" in feats


def test_unit_preview_endpoints_pass_move_validation() -> None:
    server = _hexdemo_server()
    st = server.action_manager.current_state
    unit_id = next(
        uid for uid, u in st.board.units.items() if u.active and u.faction == "union"
    )
    player_faction = "union"
    preview = compute_unit_drag_preview(
        state=st,
        unit_id=unit_id,
        player_faction=player_faction,
        board_hexes=server._iter_board_hexes(st),
        retreat_hexes_remaining=server._retreat_obligation_hexes_remaining,
        faction_has_pending_retreat=server._faction_has_pending_retreat,
        movement_budget_for_unit=server._movement_budget_for_unit,
        zoc_hexes_for_unit=server._zoc_hexes_for_unit,
        max_active_units_per_hex=server._max_active_units_per_hex,
        movement_step_cost_fn=server._movement_step_cost_fn,
        retreat_blocked_hexes=server.hooks.modification.retreat_blocked,
    )
    assert preview.kind == "move"
    budget = server._movement_budget_for_unit(st, unit_id)
    zoc = server._zoc_hexes_for_unit(st, unit_id)
    max_stack = server._max_active_units_per_hex(st, unit_id)
    step_fn = server._movement_step_cost_fn(unit_id)
    for row in preview.hexes:
        dest = Hex(int(row["i"]), int(row["j"]), int(row["k"]))
        assert is_valid_move(
            st,
            unit_id,
            dest,
            budget,
            zoc_hexes=zoc,
            max_active_units_per_hex=max_stack,
            step_cost=step_fn,
        ), f"preview hex {dest} failed is_valid_move"
