"""Preview consult fields: disable_end_phase, draft_presentation_id."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
if GAMES not in sys.path:
    sys.path.insert(0, GAMES)

from hexengine.arcs import ArcCursor, with_arc_cursor
from hexengine.gamedef.interactions import InteractionKind
from hexengine.hexes.types import Hex
from hexengine.server.map_selection import compute_map_selection_preview
from hexengine.server.protocol import MapSelectionPreviewWire


def test_map_selection_preview_wire_round_trip_policy_fields() -> None:
    wire = MapSelectionPreviewWire(
        kind="attack_plan",
        status_text="x",
        confirm_enabled=False,
        disable_end_phase=True,
        draft_presentation_id="attack_draft",
    )
    msg = wire.to_message()
    back = MapSelectionPreviewWire.from_message(msg)
    assert back.disable_end_phase is True
    assert back.draft_presentation_id == "attack_draft"


def test_attack_plan_preview_sets_dock_policy_when_target_set() -> None:
    from hexdemo.game_config import (
        HexdemoGameDefinition,
        default_match_config,
        game_definition_from_config,
    )
    from hexengine.scenarios import load_scenario
    from hexengine.scenarios.loader import scenario_to_initial_state
    from hexengine.server.game_server import GameServer

    scenario_path = (
        REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
    )
    scenario_data = load_scenario(scenario_path)
    gd = HexdemoGameDefinition(game_definition_from_config(default_match_config()))
    st = scenario_to_initial_state(
        scenario_data,
        initial_faction="union",
        initial_phase="Combat",
        phase_actions_remaining=4,
        schedule_index=0,
        game_definition=gd,
    )
    server = GameServer(
        initial_state=st,
        game_definition=gd,
        pack_id="hexdemo",
        pack_root=REPO_ROOT / "games" / "hexdemo",
    )
    st = server.action_manager.current_state
    st = with_arc_cursor(st, ArcCursor(arc_id="union_combat", segment_id="routine"))
    server.action_manager.replace_state(st)
    shell = dict(server.game_data.shell_ui or {})
    board = server._iter_board_hexes(st)

    target_hex: Hex | None = None
    for v in st.board.units.values():
        if v.active and v.faction != "union":
            target_hex = v.position
            break
    assert target_hex is not None

    idle = compute_map_selection_preview(
        state=st,
        player_faction="union",
        kind=InteractionKind.ATTACK_PLAN,
        draft={},
        shell_ui=shell,
        board_hexes=board,
        hooks=server.hooks,
    )
    assert idle.get("disable_end_phase") is None
    assert idle.get("draft_presentation_id") is None

    with_target = compute_map_selection_preview(
        state=st,
        player_faction="union",
        kind=InteractionKind.ATTACK_PLAN,
        draft={
            "target_hex": {
                "i": int(target_hex.i),
                "j": int(target_hex.j),
                "k": int(target_hex.k),
            },
        },
        shell_ui=shell,
        board_hexes=board,
        hooks=server.hooks,
    )
    assert with_target.get("disable_end_phase") is True
    assert with_target.get("draft_presentation_id") == "attack_draft"
