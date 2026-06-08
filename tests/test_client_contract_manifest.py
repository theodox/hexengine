"""Title client_contract manifest (game_data.toml → turn_rules wire)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = str(REPO_ROOT / "src")
GAMES = str(REPO_ROOT / "games")
for p in (SRC, GAMES):
    if p not in sys.path:
        sys.path.insert(0, p)

from hexengine.gamedef.client_contract import client_contract_manifest_from_mapping
from hexengine.gamedef.client_title_data import ClientTitleData
from hexengine.gamedef.game_data_toml import load_game_data_for_pack_root
from hexengine.game.arcs.client_panel_actions import panel_action_routes_for_game
from hexengine.server.game_server import GameServer


class _GameWithManifest:
    def _client_title_data(self) -> ClientTitleData:
        return ClientTitleData.from_turn_rules(
            {
                "client_contract": {
                    "schema": 1,
                    "features": ["map_selection_previews"],
                    "select_modes": [
                        {
                            "kind": "attack_plan",
                            "apply_method": "_apply_attack_plan_preview",
                            "draft_active_method": "_attack_plan_draft_active",
                            "draft_presentation_id": "attack_draft",
                        }
                    ],
                    "panel_action_routes": [
                        {
                            "mode": "local",
                            "match_action_type": "AttackPlanCancel",
                            "method": "cancel_attack_plan",
                        }
                    ],
                }
            }
        )


def test_hexdemo_game_data_loads_client_contract() -> None:
    gd = load_game_data_for_pack_root(REPO_ROOT / "games" / "hexdemo")
    assert gd.client_contract is not None
    kinds = {r.kind for r in gd.client_contract.select_modes}
    assert kinds == {"attack_plan", "retreat_path", "place_marker"}
    assert len(gd.client_contract.panel_action_routes) == 7


def test_manifest_from_mapping_ignores_empty_table() -> None:
    assert client_contract_manifest_from_mapping({}) is None
    assert client_contract_manifest_from_mapping({"schema": 1}) is None


def test_panel_action_routes_prefer_title_manifest() -> None:
    routes = panel_action_routes_for_game(_GameWithManifest())
    assert len(routes) == 1
    assert routes[0].method == "cancel_attack_plan"


def test_hexdemo_turn_rules_includes_client_contract_rows() -> None:
    from hexdemo.game_config import (
        HexdemoGameDefinition,
        default_match_config,
        game_definition_from_config,
    )
    from hexengine.scenarios import load_scenario
    from hexengine.scenarios.loader import scenario_to_initial_state

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
    cc = server._turn_rules_wire().get("client_contract", {})
    assert "attack_plan" in {r["kind"] for r in cc.get("select_modes", [])}
    assert any(
        r.get("match_action_type") == "Attack"
        for r in cc.get("panel_action_routes", [])
    )
