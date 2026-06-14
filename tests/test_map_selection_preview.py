"""Map-selection preview (attack plan draft → server legality + commit payload)."""

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
from hexengine.server.game_server import GameServer
from hexengine.server.map_selection import compute_map_selection_preview


def _hexdemo_server() -> GameServer:
    from hexdemo.game_config import (
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


def test_turn_rules_advertises_map_selection_previews() -> None:
    server = _hexdemo_server()
    tr = server._turn_rules_wire()
    feats = tr.get("client_contract", {}).get("features", [])
    assert "map_selection_previews" in feats


def test_attack_plan_preview_lists_targets_in_combat() -> None:
    server = _hexdemo_server()
    st = server.action_manager.current_state
    st = with_arc_cursor(st, ArcCursor(arc_id="union_combat", segment_id="routine"))
    server.action_manager.replace_state(st)
    raw = compute_map_selection_preview(
        state=st,
        player_faction="union",
        kind=InteractionKind.ATTACK_PLAN,
        draft={},
        shell_ui=dict(server.game_data.shell_ui or {}),
        board_hexes=server._iter_board_hexes(st),
        hooks=server.hooks,
    )
    assert raw.get("kind") == InteractionKind.ATTACK_PLAN
    targets = raw.get("valid_target_hexes") or []
    assert isinstance(targets, list)
    assert len(targets) > 0


def test_attack_plan_preview_confirm_payload_when_draft_valid() -> None:
    from hexengine.hexes.math import distance

    server = _hexdemo_server()
    st = server.action_manager.current_state
    shell = dict(server.game_data.shell_ui or {})
    board = server._iter_board_hexes(st)

    target_hex: Hex | None = None
    attacker_id: str | None = None
    for u in st.board.units.values():
        if not u.active or u.faction != "union":
            continue
        if str(u.unit_type).lower() not in ("infantry", "inf"):
            continue
        for v in st.board.units.values():
            if not v.active or v.faction == "union":
                continue
            if distance(u.position, v.position) == 1:
                target_hex = v.position
                attacker_id = u.unit_id
                break
        if target_hex is not None:
            break
    if target_hex is None or attacker_id is None:
        return

    raw = compute_map_selection_preview(
        state=st,
        player_faction="union",
        kind=InteractionKind.ATTACK_PLAN,
        draft={
            "target_hex": {
                "i": int(target_hex.i),
                "j": int(target_hex.j),
                "k": int(target_hex.k),
            },
            "attacker_ids": [attacker_id],
        },
        shell_ui=shell,
        board_hexes=board,
        hooks=server.hooks,
    )
    assert attacker_id in (raw.get("eligible_attacker_ids") or [])
    assert raw.get("confirm_enabled") is True
    commit = raw.get("commit_payload")
    assert isinstance(commit, dict)
    assert commit.get("attacker_id") == attacker_id
