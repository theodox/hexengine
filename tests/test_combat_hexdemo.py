"""Hexdemo adjacent combat: hooks, retreat moves, combat_event fanout."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from hexengine.hexes.math import neighbors
from hexengine.hexes.types import Hex
from hexengine.gamedef.builtin import default_game_definition
from hexengine.server.game_server import GameServer
from hexengine.server.protocol import ActionRequest, CombatEventWire, PlayerInfo
from hexengine.state import GameState
from hexengine.state.actions import Attack, NextPhase
from hexengine.state.game_state import BoardState, TurnState, UnitState

from games.hexdemo.game_config import game_definition_from_config, default_match_config


def _hexdemo_combat_state() -> GameState:
    """Union combat phase with two adjacent units (union attacker, confederate defender)."""
    h0 = Hex(0, 0, 0)
    h1 = next(neighbors(h0))
    board = BoardState(
        units={
            "u_att": UnitState(
                unit_id="u_att",
                unit_type="inf",
                faction="union",
                position=h0,
                health=100,
                active=True,
            ),
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="inf",
                faction="confederate",
                position=h1,
                health=100,
                active=True,
            ),
        }
    )
    turn = TurnState(
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=2,
        turn_number=1,
        schedule_index=1,
    )
    return GameState(board=board, turn=turn, extension={"hexdemo": {}}, rng_log=())


def _hexdemo_two_union_vs_one_def() -> GameState:
    """Union combat with two union units adjacent to one defender."""
    d1 = Hex(0, 0, 0)
    u1 = Hex(1, -1, 0)
    u2 = Hex(1, 0, -1)
    board = BoardState(
        units={
            "u_a": UnitState(
                unit_id="u_a",
                unit_type="inf",
                faction="union",
                position=u1,
                health=100,
                active=True,
            ),
            "u_b": UnitState(
                unit_id="u_b",
                unit_type="inf",
                faction="union",
                position=u2,
                health=100,
                active=True,
            ),
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="inf",
                faction="confederate",
                position=d1,
                health=100,
                active=True,
            ),
        }
    )
    turn = TurnState(
        current_faction="union",
        current_phase="Combat",
        phase_actions_remaining=2,
        turn_number=1,
        schedule_index=1,
    )
    return GameState(board=board, turn=turn, extension={"hexdemo": {}}, rng_log=())


def test_hexdemo_retreat_reads_extension() -> None:
    """Mandatory retreat steps live in extension; engine helper has no UI imports."""
    from hexengine.state.hexdemo_retreat import retreat_hexes_remaining

    st = _hexdemo_combat_state()
    ext = dict(st.extension)
    hx = dict(ext.get("hexdemo", {}))
    hx["retreat_obligations"] = {"u_def": 2}
    st2 = st.with_extension({**ext, "hexdemo": hx})
    assert retreat_hexes_remaining(st2, "u_def") == 2
    assert retreat_hexes_remaining(st2, "u_att") is None


def test_server_suggested_focus_unit_id_for_player(hexdemo_server: GameServer) -> None:
    """``GameServer`` fills ``StateUpdate.suggested_focus_unit_id`` from the title hook."""
    from hexengine.server.protocol import PlayerInfo

    st = hexdemo_server.action_manager.current_state
    ext = dict(st.extension)
    hx = dict(ext.get("hexdemo", {}))
    hx["retreat_obligations"] = {"u_def": 1}
    new_st = st.with_extension({**ext, "hexdemo": hx})
    hexdemo_server.action_manager._current_state = new_st

    hexdemo_server.players["p_conf"] = PlayerInfo(
        player_id="p_conf",
        player_name="C",
        faction="confederate",
        connected=True,
    )
    assert hexdemo_server._suggested_focus_unit_id_for_player_id("p_conf") == "u_def"

    hexdemo_server.players["p_uni"] = PlayerInfo(
        player_id="p_uni",
        player_name="U",
        faction="union",
        connected=True,
    )
    assert hexdemo_server._suggested_focus_unit_id_for_player_id("p_uni") is None

    ob = hexdemo_server._retreat_obligations_for_player_id("p_conf")
    assert ob == {"u_def": 1}
    assert hexdemo_server._retreat_obligations_for_player_id("p_uni") is None


@pytest.fixture()
def hexdemo_server() -> GameServer:
    gd = game_definition_from_config(default_match_config())
    return GameServer(
        initial_state=_hexdemo_combat_state(),
        game_definition=gd,
    )


def test_hexdemo_validate_attack_adjacent_and_once_per_unit(hexdemo_server: GameServer) -> None:
    gd = hexdemo_server._game_definition
    st = hexdemo_server.action_manager.current_state
    gd.validate_attack_request(
        st,
        player_faction="union",
        attack_kind="adjacent",
        params={"attacker_id": "u_att", "defender_id": "u_def"},
    )
    far = Hex(4, -4, 0)
    du = st.board.units["u_def"].with_position(far)
    st_bad = st.with_board(st.board.with_unit(du))
    with pytest.raises(ValueError, match="adjacent"):
        gd.validate_attack_request(
            st_bad,
            player_faction="union",
            attack_kind="adjacent",
            params={"attacker_id": "u_att", "defender_id": "u_def"},
        )

    with (
        patch("hexengine.state.actions.random.choice", return_value="none"),
        patch("hexengine.state.actions.random.randint", return_value=1),
    ):
        hexdemo_server.action_manager.execute(
            Attack("adjacent", "u_att", "u_def"),
        )
    st2 = hexdemo_server.action_manager.current_state
    with pytest.raises(ValueError, match="already attacked"):
        gd.validate_attack_request(
            st2,
            player_faction="union",
            attack_kind="adjacent",
            params={"attacker_id": "u_att", "defender_id": "u_def"},
        )


def test_attack_updates_extension_and_rng() -> None:
    st = _hexdemo_combat_state()
    with (
        patch("hexengine.state.actions.random.choice", return_value="none"),
        patch("hexengine.state.actions.random.randint", return_value=1),
    ):
        nxt = Attack("adjacent", "u_att", "u_def").apply(st)
    hx = nxt.extension.get("hexdemo")
    assert isinstance(hx, dict)
    assert hx.get("attacks_this_phase") == ["u_att"]
    assert nxt.rng_log[-1]["op"] == "adjacent_attack"
    assert nxt.rng_log[-1]["outcome"] == "none"


def test_combat_event_fanout_retreat_vs_wait(hexdemo_server: GameServer) -> None:
    server = hexdemo_server
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.players["p_c"] = PlayerInfo(
        player_id="p_c", player_name="C", faction="confederate", connected=True
    )
    server.faction_to_player["union"] = "p_u"
    server.faction_to_player["confederate"] = "p_c"

    captured: list[tuple[str, str, dict]] = []

    def cap(pid: str, msg) -> None:
        captured.append((pid, msg.type, msg.payload))

    server.add_message_handler(cap)

    async def run() -> None:
        with (
            patch(
                "hexengine.state.actions.random.choice",
                return_value="defender_retreat",
            ),
            patch("hexengine.state.actions.random.randint", return_value=2),
        ):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "adjacent",
                    "attacker_id": "u_att",
                    "defender_id": "u_def",
                },
                player_id="p_u",
            )
            await server.handle_message("p_u", req.to_message())

    asyncio.run(run())

    combat_msgs = [c for c in captured if c[1] == CombatEventWire.wire_type]
    assert len(combat_msgs) == 2
    by_pid = {pid: payload for pid, _, payload in combat_msgs}
    assert by_pid["p_c"]["instruction"] == "retreat_required"
    assert by_pid["p_c"]["retreat_unit_id"] == "u_def"
    assert by_pid["p_c"]["retreat_hexes_remaining"] == 2
    assert by_pid["p_u"]["instruction"] == "wait"


def test_builtin_game_rejects_attack() -> None:
    server = GameServer(
        initial_state=_hexdemo_combat_state(),
        game_definition=default_game_definition(),
    )
    server.players["p1"] = PlayerInfo(
        player_id="p1", player_name="A", faction="union", connected=True
    )

    async def run() -> str | None:
        captured: list[str] = []

        def cap(_pid: str, msg) -> None:
            if msg.type == "error":
                captured.append(str(msg.payload.get("error", "")))

        server.add_message_handler(cap)
        req = ActionRequest(
            action_type="Attack",
            params={
                "attack_kind": "adjacent",
                "attacker_id": "u_att",
                "defender_id": "u_def",
            },
            player_id="p1",
        )
        await server.handle_message("p1", req.to_message())
        return captured[0] if captured else None

    err = asyncio.run(run())
    assert err is not None
    assert "not support" in err.lower()


def test_retreat_move_no_spend_action(hexdemo_server: GameServer) -> None:
    server = hexdemo_server
    st = server.action_manager.current_state
    h0 = st.board.units["u_att"].position
    h3 = Hex(2, -2, 0)

    ext = dict(st.extension)
    hx = dict(ext.get("hexdemo", {}))
    hx["retreat_obligations"] = {"u_att": 2}
    hx["combat_gate"] = "awaiting_retreat"
    ext["hexdemo"] = hx
    server.action_manager.replace_state(st.with_extension(ext))

    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.faction_to_player["union"] = "p_u"

    remaining_before = server.action_manager.current_state.turn.phase_actions_remaining

    async def run() -> None:
        params = {
            "unit_id": "u_att",
            "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
            "to_hex": {"i": h3.i, "j": h3.j, "k": h3.k},
        }
        req = ActionRequest(
            action_type="MoveUnit",
            params=params,
            player_id="p_u",
        )
        await server.handle_message("p_u", req.to_message())

    asyncio.run(run())
    after = server.action_manager.current_state
    assert after.turn.phase_actions_remaining == remaining_before
    ro = after.extension.get("hexdemo", {}).get("retreat_obligations", {})
    assert "u_att" not in ro


def test_clear_hexdemo_combat_on_next_phase(hexdemo_server: GameServer) -> None:
    server = hexdemo_server
    with (
        patch("hexengine.state.actions.random.choice", return_value="none"),
        patch("hexengine.state.actions.random.randint", return_value=1),
    ):
        server.action_manager.execute(Attack("adjacent", "u_att", "u_def"))
    assert server.action_manager.current_state.extension["hexdemo"].get(
        "attacks_this_phase"
    )
    info = server._get_next_phase()
    server.action_manager.execute(
        NextPhase(
            new_faction=info["faction"],
            new_phase=info["phase"],
            max_actions=info["max_actions"],
            new_schedule_index=int(info["schedule_index"]),
        )
    )
    server._after_next_phase_applied()
    hx = server.action_manager.current_state.extension.get("hexdemo", {})
    assert "attacks_this_phase" not in hx
    assert "last_combat" not in hx


def test_auto_advance_when_sole_attacker_has_attacked(hexdemo_server: GameServer) -> None:
    server = hexdemo_server
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.faction_to_player["union"] = "p_u"

    async def run() -> None:
        with (
            patch("hexengine.state.actions.random.choice", return_value="none"),
            patch("hexengine.state.actions.random.randint", return_value=1),
        ):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "adjacent",
                    "attacker_id": "u_att",
                    "defender_id": "u_def",
                },
                player_id="p_u",
            )
            await server.handle_message("p_u", req.to_message())

    asyncio.run(run())
    st = server.action_manager.current_state
    assert st.turn.current_phase == "Move"
    assert st.turn.current_faction == "confederate"
    assert st.turn.schedule_index == 2


def test_no_auto_advance_while_retreat_pending(hexdemo_server: GameServer) -> None:
    server = hexdemo_server
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.players["p_c"] = PlayerInfo(
        player_id="p_c", player_name="C", faction="confederate", connected=True
    )
    server.faction_to_player["union"] = "p_u"
    server.faction_to_player["confederate"] = "p_c"

    async def run() -> None:
        with (
            patch(
                "hexengine.state.actions.random.choice",
                return_value="defender_retreat",
            ),
            patch("hexengine.state.actions.random.randint", return_value=1),
        ):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "adjacent",
                    "attacker_id": "u_att",
                    "defender_id": "u_def",
                },
                player_id="p_u",
            )
            await server.handle_message("p_u", req.to_message())

    asyncio.run(run())
    st = server.action_manager.current_state
    assert st.turn.current_phase == "Combat"
    assert st.turn.current_faction == "union"


def test_two_union_units_require_two_attacks_before_advance() -> None:
    gd = game_definition_from_config(default_match_config())
    server = GameServer(initial_state=_hexdemo_two_union_vs_one_def(), game_definition=gd)
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.faction_to_player["union"] = "p_u"

    async def attack(attacker: str) -> None:
        with (
            patch("hexengine.state.actions.random.choice", return_value="none"),
            patch("hexengine.state.actions.random.randint", return_value=1),
        ):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "adjacent",
                    "attacker_id": attacker,
                    "defender_id": "u_def",
                },
                player_id="p_u",
            )
            await server.handle_message("p_u", req.to_message())

    async def run() -> None:
        await attack("u_a")
        st1 = server.action_manager.current_state
        assert st1.turn.current_phase == "Combat"
        assert st1.turn.current_faction == "union"
        await attack("u_b")

    asyncio.run(run())
    st = server.action_manager.current_state
    assert st.turn.current_phase == "Move"
    assert st.turn.current_faction == "confederate"
