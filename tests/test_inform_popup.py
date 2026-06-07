"""INFORM lane: inform inspect → title hook → ui_popup."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
if GAMES not in sys.path:
    sys.path.insert(0, GAMES)

from hexengine.hexes.types import Hex
from hexengine.hooks.inform_popup import InformPopupContext
from hexengine.server.game_server import GameServer
from hexengine.server.protocol import InspectRequest
from hexengine.state import GameState


def _hexdemo_server() -> GameServer:
    from games.hexdemo.game_config import (
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


def test_hexdemo_inform_popup_attack_plan_shell_ui() -> None:
    from games.hexdemo.hooks.ui import inform_popup_for_viewer

    server = _hexdemo_server()
    st = server.action_manager.current_state
    h = Hex(0, 0, 0)
    shell = dict(server.game_data.shell_ui or {})
    ctx = InformPopupContext(
        state=st,
        viewer_faction="union",
        target_kind="inform",
        target_id="no_attackable_enemy",
        inform_kind="attack_plan",
        reason="no_attackable_enemy",
        anchor_hex=h,
        unit_id=None,
        shell_ui=shell,
    )
    from hexengine.hooks.internal.ui_wire import inform_popup_to_wire

    pm = inform_popup_to_wire(inform_popup_for_viewer(ctx))
    assert "attackable" in str(pm.get("text", "")).lower()
    assert pm.get("ttl_ms") == 750


def test_server_inform_inspect_returns_ui_popup() -> None:
    import asyncio

    from hexengine.server.protocol import JoinGameRequest

    server = _hexdemo_server()
    pid = "test-inform-player"
    h = Hex(3, -1, -2)
    sent: list = []

    async def capture(_pid: str, wire) -> None:
        sent.append(wire)

    async def run() -> None:
        await server.handle_message(
            pid,
            JoinGameRequest(player_name="Tester", faction="union").to_message(),
        )
        orig = server._send_message
        server._send_message = capture  # type: ignore[method-assign]
        try:
            req = InspectRequest(
                target_kind="inform",
                target_id="no_attackable_enemy",
                context={
                    "inform_kind": "attack_plan",
                    "hex": {"i": int(h.i), "j": int(h.j), "k": int(h.k)},
                },
            )
            await server._handle_inspect_request(pid, req.to_message())
        finally:
            server._send_message = orig  # type: ignore[method-assign]

    asyncio.run(run())
    assert sent
    msg = sent[-1]
    payload = msg.payload if hasattr(msg, "payload") else {}
    assert str(payload.get("text", "")).strip()
    assert "attackable" in str(payload.get("text", "")).lower()
    assert payload.get("ttl_ms") == 750


def _hexdemo_combat_segment_server() -> GameServer:
    """Server on union Combat routine slot (``inform_profile`` on wire)."""

    from games.hexdemo.game_config import (
        default_match_config,
        game_definition_from_config,
    )

    from hexengine.state.game_state import TurnState

    st = GameState.create_empty().with_turn(TurnState("union", "Combat", 4, 1, 1, 0))
    return GameServer(
        initial_state=st,
        game_definition=game_definition_from_config(default_match_config()),
        pack_id="hexdemo",
        pack_root=REPO_ROOT / "games" / "hexdemo",
    )


def test_server_inform_inspect_defaults_attack_plan_profile() -> None:
    """Omit client ``inform_kind``; server uses ``current_segment.inform_profile``."""

    import asyncio

    from hexengine.server.protocol import JoinGameRequest

    server = _hexdemo_combat_segment_server()
    pid = "test-inform-profile-default"
    h = Hex(3, -1, -2)
    sent: list = []

    async def capture(_pid: str, wire) -> None:
        sent.append(wire)

    async def run() -> None:
        await server.handle_message(
            pid,
            JoinGameRequest(player_name="Tester", faction="union").to_message(),
        )
        orig = server._send_message
        server._send_message = capture  # type: ignore[method-assign]
        try:
            req = InspectRequest(
                target_kind="inform",
                target_id="no_attackable_enemy",
                context={
                    "hex": {"i": int(h.i), "j": int(h.j), "k": int(h.k)},
                },
            )
            await server._handle_inspect_request(pid, req.to_message())
        finally:
            server._send_message = orig  # type: ignore[method-assign]

    asyncio.run(run())
    assert sent
    payload = sent[-1].payload if hasattr(sent[-1], "payload") else {}
    assert "attackable" in str(payload.get("text", "")).lower()
    assert payload.get("ttl_ms") == 750


def test_inform_popup_wire_round_trip_preserves_ttl_ms() -> None:
    from hexengine.server.protocol import UIPopupWire

    wire = UIPopupWire(
        hex={"i": 0, "j": 0, "k": 0},
        text="x",
        ttl_ms=750,
    )
    msg = wire.to_message()
    back = UIPopupWire.from_message(msg)
    assert back.ttl_ms == 750
