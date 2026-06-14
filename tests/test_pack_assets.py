"""Pack asset URL helpers and turn_rules.asset_base_url."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HEXDEMO_ROOT = REPO_ROOT / "games" / "hexdemo"
GAMES = str(REPO_ROOT / "games")
if GAMES not in sys.path:
    sys.path.insert(0, GAMES)


def test_pack_asset_base_url() -> None:
    from hexengine.game_packs.resources import pack_asset_base_url

    assert pack_asset_base_url("hexdemo") == "/pack/hexdemo/"
    assert pack_asset_base_url("../evil") is None


def test_pack_asset_url_pack_route() -> None:
    from hexengine.game_packs.resources import pack_asset_url

    href = pack_asset_url(
        HEXDEMO_ROOT,
        "flags/union_34star.svg",
        asset_base_url="/pack/hexdemo/",
    )
    assert href == "/pack/hexdemo/flags/union_34star.svg"


def test_pack_asset_href_without_asset_base_url_returns_none() -> None:
    from hexengine.ui.display import pack_asset_href

    assert pack_asset_href(HEXDEMO_ROOT, "ui.css") is None


def test_pack_resource_site_href_under_repo_static_root() -> None:
    from hexengine.game_packs.resources import pack_resource_site_href

    href = pack_resource_site_href(HEXDEMO_ROOT, "ui.css", static_root=REPO_ROOT)
    assert href is not None
    assert href.startswith("/")
    assert href.replace("\\", "/").endswith("games/hexdemo/resources/ui.css")


def test_turn_rules_asset_base_url_hexdemo() -> None:
    from hexdemo.game_config import (
        default_match_config,
        game_definition_from_config,
    )
    from hexengine.scenarios import load_scenario
    from hexengine.scenarios.loader import scenario_to_initial_state
    from hexengine.server.game_server import GameServer

    scenario_path = HEXDEMO_ROOT / "scenarios" / "default" / "scenario.toml"
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
    server = GameServer(
        initial_state=st,
        game_definition=gd,
        pack_id="hexdemo",
        pack_root=HEXDEMO_ROOT,
    )
    tr = server._turn_rules_wire()
    assert tr.get("asset_base_url") == "/pack/hexdemo/"
    fu = tr.get("faction_ui") or {}
    assert fu.get("css_href") == "/pack/hexdemo/ui.css"


def test_resolve_pack_static_file() -> None:
    from hexengine.dev.static_server import resolve_pack_static_file

    path = resolve_pack_static_file(
        REPO_ROOT / "games",
        "/pack/hexdemo/flags/union_34star.svg",
    )
    assert path is not None
    assert path.name == "union_34star.svg"
