"""Map-selection preview for marker click-confirm relocate (place_marker)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
if GAMES not in sys.path:
    sys.path.insert(0, GAMES)

from hexengine.gamedef.interactions import InteractionKind
from hexengine.hexes.types import Hex, HexColRow
from hexengine.server.map_selection import compute_map_selection_preview


def _hexdemo_server():
    from games.hexdemo.game_config import (
        HexdemoGameDefinition,
        default_match_config,
        game_definition_from_config,
    )
    from hexengine.scenarios import load_scenario
    from hexengine.scenarios.loader import scenario_to_initial_state
    from hexengine.server.game_server import GameServer

    scenario_path = REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
    scenario_data = load_scenario(scenario_path)
    gd = HexdemoGameDefinition(game_definition_from_config(default_match_config()))
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
        game_definition=gd,
        pack_id="hexdemo",
        pack_root=REPO_ROOT / "games" / "hexdemo",
        markers=scenario_data.markers_to_wire_list(),
    )


def test_place_marker_preview_lists_legal_hexes() -> None:
    server = _hexdemo_server()
    st = server.action_manager.current_state
    markers = [dict(m) for m in server.markers if isinstance(m, dict)]
    assert markers
    mid = str(markers[0].get("id", "")).strip()
    raw = compute_map_selection_preview(
        state=st,
        player_faction="union",
        kind=InteractionKind.PLACE_MARKER,
        draft={"marker_id": mid},
        shell_ui=dict(server.game_data.shell_ui or {}),
        board_hexes=server._iter_board_hexes(st),
        hooks=server.hooks,
        markers=markers,
    )
    assert raw.get("kind") == InteractionKind.PLACE_MARKER
    legal = raw.get("valid_target_hexes") or []
    assert isinstance(legal, list)
    assert len(legal) > 0
    actions = raw.get("panel_actions") or []
    ids = {str(a.get("id", "")) for a in actions if isinstance(a, dict)}
    assert "place_marker_confirm" in ids
    assert "place_marker_cancel" in ids


def test_place_marker_preview_confirm_when_destination_differs() -> None:
    server = _hexdemo_server()
    st = server.action_manager.current_state
    markers = [dict(m) for m in server.markers if isinstance(m, dict)]
    row = markers[0]
    mid = str(row.get("id", "")).strip()
    pos = row.get("position")
    assert isinstance(pos, list | tuple) and len(pos) == 2
    from_hex = Hex.from_hex_col_row(HexColRow(col=int(pos[0]), row=int(pos[1])))

    dest: Hex | None = None
    for h in server._iter_board_hexes(st):
        if h != from_hex:
            dest = h
            break
    assert dest is not None

    raw = compute_map_selection_preview(
        state=st,
        player_faction="union",
        kind=InteractionKind.PLACE_MARKER,
        draft={
            "marker_id": mid,
            "to_hex": {"i": int(dest.i), "j": int(dest.j), "k": int(dest.k)},
        },
        shell_ui=dict(server.game_data.shell_ui or {}),
        board_hexes=server._iter_board_hexes(st),
        hooks=server.hooks,
        markers=markers,
    )
    assert raw.get("confirm_enabled") is True
    commit = raw.get("commit_payload")
    assert isinstance(commit, dict)
    assert commit.get("marker_id") == mid
    assert commit.get("to_position") == [
        int(HexColRow.from_hex(dest).col),
        int(HexColRow.from_hex(dest).row),
    ]
