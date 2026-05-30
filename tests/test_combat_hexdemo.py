"""Hexdemo adjacent combat: hooks, retreat moves, combat_event fanout."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from games.hexdemo.game_config import default_match_config, game_definition_from_config

from hexengine.gamedef.builtin import default_game_definition
from hexengine.hexes.math import neighbors
from hexengine.hexes.types import Hex
from hexengine.server.game_server import GameServer
from hexengine.server.protocol import ActionRequest, CombatEventWire, PlayerInfo
from hexengine.state import GameState
from hexengine.state.title_extension import title_bucket
from hexengine.state.actions import Attack, NextPhase
from hexengine.state.game_state import BoardState, TurnState, UnitState


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
    return GameState(board=board, turn=turn, title_state={}, title_bucket_key="hexdemo", rng_log=())


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
    return GameState(board=board, turn=turn, title_state={}, title_bucket_key="hexdemo", rng_log=())


def _hexdemo_artillery_ranged_vs_infantry() -> GameState:
    """Union artillery at range 2 vs confederate infantry (melee on defender hex only)."""
    h_def = Hex(0, 0, 0)
    h_art = Hex(2, -1, -1)
    # Second union unit avoids auto-advance clearing `last_combat` after one attack.
    h_idle = Hex(5, -5, 0)
    board = BoardState(
        units={
            "u_art": UnitState(
                unit_id="u_art",
                unit_type="artillery",
                faction="union",
                position=h_art,
                health=100,
                active=True,
                attributes={"combat": 5, "morale": 6, "range": 4},
            ),
            "u_idle": UnitState(
                unit_id="u_idle",
                unit_type="infantry",
                faction="union",
                position=h_idle,
                health=100,
                active=True,
                attributes={"combat": 1, "morale": 1},
            ),
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="infantry",
                faction="confederate",
                position=h_def,
                health=100,
                active=True,
                attributes={"combat": 4, "morale": 4},
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
    return GameState(board=board, turn=turn, title_state={}, title_bucket_key="hexdemo", rng_log=())


def test_pack_extension_retreat_reads_custom_key() -> None:
    from hexengine.state.pack_extension_retreat import retreat_hexes_remaining

    st = GameState.create_empty()
    st = st.with_title_state(
        {"retreat_obligations": {"u": 3}}, title_bucket_key="other"
    )
    assert retreat_hexes_remaining(st, "u", extension_key="other") == 3


def test_hexdemo_retreat_reads_extension() -> None:
    """Mandatory retreat steps live in extension; engine helper has no UI imports."""
    from hexengine.state.pack_extension_retreat import retreat_hexes_remaining

    from hexengine.state.title_extension import title_bucket

    st = _hexdemo_combat_state()
    hx = dict(title_bucket(st, "hexdemo"))
    hx["retreat_obligations"] = {"u_def": 2}
    st2 = st.with_title_state(hx, title_bucket_key="hexdemo")
    assert retreat_hexes_remaining(st2, "u_def", extension_key="hexdemo") == 2
    assert retreat_hexes_remaining(st2, "u_att", extension_key="hexdemo") is None


def test_hexdemo_stacking_limit_rejects_move() -> None:
    """Server rejects MoveUnit into a hex already holding 3 active units."""
    from hexengine.server.protocol import ActionRequest, JoinGameRequest
    from hexengine.state.game_state import BoardState, TurnState, UnitState

    h0 = Hex(0, 0, 0)
    h1 = next(neighbors(h0))
    board = BoardState(
        units={
            "mover": UnitState(
                unit_id="mover",
                unit_type="inf",
                faction="union",
                position=h0,
                health=100,
                active=True,
            ),
            "s1": UnitState(
                unit_id="s1",
                unit_type="inf",
                faction="union",
                position=h1,
                health=100,
                active=True,
                stack_index=0,
            ),
            "s2": UnitState(
                unit_id="s2",
                unit_type="inf",
                faction="union",
                position=h1,
                health=100,
                active=True,
                stack_index=1,
            ),
            "s3": UnitState(
                unit_id="s3",
                unit_type="inf",
                faction="union",
                position=h1,
                health=100,
                active=True,
                stack_index=2,
            ),
        }
    )
    turn = TurnState(
        current_faction="union",
        current_phase="Move",
        phase_actions_remaining=2,
        schedule_index=0,
    )
    st = GameState(board=board, turn=turn, title_state={}, title_bucket_key="hexdemo", rng_log=())
    gd = game_definition_from_config(default_match_config())
    server = GameServer(initial_state=st, game_definition=gd)

    async def run() -> None:
        out: list[dict] = []
        server.add_message_handler(lambda _pid, msg: out.append(msg.payload))
        await server.handle_message(
            "p1", JoinGameRequest(player_name="Alice", faction="union").to_message()
        )
        req = ActionRequest(
            action_type="MoveUnit",
            params={
                "unit_id": "mover",
                "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
                "to_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
            },
            player_id="p1",
        )
        # Capture outgoing messages to observe the error.
        out: list[dict] = []
        server.add_message_handler(lambda _pid, msg: out.append(msg.payload))
        await server.handle_message("p1", req.to_message())
        errors = [p.get("error") for p in out if isinstance(p, dict)]
        assert any(
            isinstance(e, str)
            and ("stacking" in e.lower() or "active units" in e.lower())
            for e in errors
        ), f"Expected stacking error, got: {errors!r}"

    asyncio.run(run())


def test_hexdemo_move_can_pass_through_friendly_stack() -> None:
    """A unit may traverse through a friendly stack, but cannot end over the limit."""
    from hexengine.state.logic import compute_valid_moves

    h0 = Hex(0, 0, 0)
    h1 = next(neighbors(h0))
    h2 = next(h for h in neighbors(h1) if h != h0)
    board = BoardState(
        units={
            "m": UnitState("m", "inf", "union", h0, active=True),
            # Friendly-occupied intermediate hex
            "s": UnitState("s", "inf", "union", h1, active=True, stack_index=0),
        }
    )
    st = GameState(
        board=board,
        turn=TurnState(
            current_faction="union", current_phase="Move", phase_actions_remaining=2
        ),
        title_state={}, title_bucket_key="hexdemo",
        rng_log=(),
    )
    moves = compute_valid_moves(st, "m", 2.0, max_active_units_per_hex=3)
    assert h2 in moves


def test_hexdemo_retreat_moves_entire_stack() -> None:
    """When a stack has retreat obligations, moving one retreats all units in the stack."""
    from hexengine.server.protocol import ActionRequest, JoinGameRequest

    h0 = Hex(0, 0, 0)
    h1 = next(neighbors(h0))
    # Retreat obligation is 1, so destination must be adjacent to h0 (but not enemy-occupied).
    h2 = next(h for h in neighbors(h0) if h != h1)
    board = BoardState(
        units={
            "u1": UnitState("u1", "inf", "union", h0, active=True, stack_index=0),
            "u2": UnitState("u2", "inf", "union", h0, active=True, stack_index=1),
        }
    )
    turn = TurnState(
        current_faction="union", current_phase="Combat", phase_actions_remaining=2
    )
    st = GameState(
        board=board,
        turn=turn,
        title_state={"retreat_obligations": {"u1": 1, "u2": 1}},
        title_bucket_key="hexdemo",
        rng_log=(),
    )
    gd = game_definition_from_config(default_match_config())
    server = GameServer(initial_state=st, game_definition=gd)

    async def run() -> None:
        out: list[dict] = []
        server.add_message_handler(lambda _pid, msg: out.append(msg.payload))
        await server.handle_message(
            "p1", JoinGameRequest(player_name="Alice", faction="union").to_message()
        )
        req = ActionRequest(
            action_type="MoveUnit",
            params={
                "unit_id": "u1",
                "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
                "to_hex": {"i": h2.i, "j": h2.j, "k": h2.k},
            },
            player_id="p1",
        )
        await server.handle_message("p1", req.to_message())
        errs = [p.get("error") for p in out if isinstance(p, dict) and "error" in p]
        assert not errs, f"Unexpected server error(s): {errs!r}"
        after = server.action_manager.current_state
        assert after.board.units["u1"].position == h2
        assert after.board.units["u2"].position == h2
        hx = title_bucket(after, "hexdemo")
        ro = hx.get("retreat_obligations", {})
        assert "u1" not in ro and "u2" not in ro

    asyncio.run(run())


def test_retreat_stack_rejected_before_partial_move() -> None:
    """Stack retreat must not move the lead unit if the full stack cannot fit at destination."""
    from hexengine.server.protocol import ActionRequest, JoinGameRequest

    h0 = Hex(0, 0, 0)
    h_dest = next(neighbors(h0))
    board = BoardState(
        units={
            "u1": UnitState("u1", "inf", "union", h0, active=True, stack_index=0),
            "u2": UnitState("u2", "inf", "union", h0, active=True, stack_index=1),
            "u3": UnitState("u3", "inf", "union", h_dest, active=True, stack_index=0),
            "u4": UnitState("u4", "inf", "union", h_dest, active=True, stack_index=1),
        }
    )
    turn = TurnState(
        current_faction="union", current_phase="Combat", phase_actions_remaining=2
    )
    st = GameState(
        board=board,
        turn=turn,
        title_state={"retreat_obligations": {"u1": 1, "u2": 1}},
        title_bucket_key="hexdemo",
        rng_log=(),
    )
    gd = game_definition_from_config(default_match_config())
    server = GameServer(initial_state=st, game_definition=gd)

    async def run() -> None:
        out: list[dict] = []
        server.add_message_handler(lambda _pid, msg: out.append(msg.payload))
        await server.handle_message(
            "p1", JoinGameRequest(player_name="Alice", faction="union").to_message()
        )
        req = ActionRequest(
            action_type="MoveUnit",
            params={
                "unit_id": "u1",
                "from_hex": {"i": h0.i, "j": h0.j, "k": h0.k},
                "to_hex": {"i": h_dest.i, "j": h_dest.j, "k": h_dest.k},
            },
            player_id="p1",
        )
        await server.handle_message("p1", req.to_message())
        errors = [p.get("error") for p in out if isinstance(p, dict)]
        assert any(
            isinstance(e, str) and "stacking" in e.lower() for e in errors
        ), f"Expected stacking rejection, got: {errors!r}"
        after = server.action_manager.current_state
        assert after.board.units["u1"].position == h0
        assert after.board.units["u2"].position == h0

    asyncio.run(run())


def test_server_suggested_focus_unit_id_for_player(hexdemo_server: GameServer) -> None:
    """`GameServer` fills `StateUpdate.suggested_focus_unit_id` from the title hook."""
    from hexengine.server.protocol import PlayerInfo

    from hexengine.state.title_extension import title_bucket

    st = hexdemo_server.action_manager.current_state
    hx = dict(title_bucket(st, "hexdemo"))
    hx["retreat_obligations"] = {"u_def": 1}
    new_st = st.with_title_state(hx, title_bucket_key="hexdemo")
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


def test_hexdemo_phase_interaction_banner_includes_html(
    hexdemo_server: GameServer,
) -> None:
    server = hexdemo_server
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    msgs = server._interaction_messages_for_player_id("p_u")
    assert msgs is not None
    phase_rows = [m for m in msgs if m.get("kind") == "phase"]
    assert phase_rows
    row = phase_rows[0]
    assert isinstance(row.get("text"), str) and row["text"]
    assert row["text"].startswith("Union:")
    html = row.get("html")
    assert isinstance(html, str)
    assert "hexdemo-turn-banner__flag--union" in html


def test_hexdemo_validate_attack_adjacent_and_once_per_unit(
    hexdemo_server: GameServer,
) -> None:
    st = hexdemo_server.action_manager.current_state
    from hexengine.hooks.attack import AttackContext

    att_h = st.board.units["u_att"].position
    def_h = st.board.units["u_def"].position
    ctx = AttackContext(
        state=st,
        attacker_ids=("u_att",),
        defender_ids=("u_def",),
        attacker_hexes=(att_h,),
        defender_hexes=(def_h,),
        player_faction="union",
        attack_kind="combined",
        params={
            "attacker_id": "u_att",
            "attacker_ids": ["u_att"],
            "defender_id": "u_def",
            "attack_kind": "combined",
        },
    )
    assert hexdemo_server.hooks.attack.validate(ctx) is None
    far = Hex(4, -4, 0)
    du = st.board.units["u_def"].with_position(far)
    st_bad = st.with_board(st.board.with_unit(du))
    with pytest.raises(ValueError, match="adjacent"):
        att_h = st_bad.board.units["u_att"].position
        def_h = st_bad.board.units["u_def"].position
        hexdemo_server.hooks.attack.validate(
            AttackContext(
                state=st_bad,
                attacker_ids=("u_att",),
                defender_ids=("u_def",),
                attacker_hexes=(att_h,),
                defender_hexes=(def_h,),
                player_faction="union",
                attack_kind="combined",
                params={
                    "attacker_id": "u_att",
                    "attacker_ids": ["u_att"],
                    "defender_id": "u_def",
                    "attack_kind": "combined",
                },
            )
        )

    hexdemo_server.action_manager.execute(
        Attack(
            "combined",
            "u_att",
            "u_def",
            outcome="none",
            retreat_distance=None,
            rng_entry={"op": "adjacent_attack", "outcome": "none"},
        )
    )
    st2 = hexdemo_server.action_manager.current_state
    # Engine `Attack` no longer writes hexdemo bucket bookkeeping; titles own that in
    # `AFTER_ATTACK_APPLIED` follow-ups. Apply hexdemo follow-ups so "already attacked"
    # validation sees `attacks_this_phase`.
    from games.hexdemo import combat_transitions
    from hexengine.hooks.attack import AfterAttackAppliedContext, AttackResolution

    att_h = st.board.units["u_att"].position
    def_h = st.board.units["u_def"].position
    follow_ctx = AfterAttackAppliedContext(
        state=st2,
        attack_context=AttackContext(
            state=st,
            attacker_ids=("u_att",),
            defender_ids=("u_def",),
            attacker_hexes=(att_h,),
            defender_hexes=(def_h,),
            player_faction="union",
            attack_kind="combined",
            params={
                "attacker_id": "u_att",
                "attacker_ids": ["u_att"],
                "defender_id": "u_def",
                "defender_ids": ["u_def"],
                "attack_kind": "combined",
            },
        ),
        resolution=AttackResolution(
            outcome="none",
            attacker_ids=None,
            defender_ids=None,
            retreat_distance=None,
            retreat_unit_id=None,
            rng_entry=None,
            effects=None,
        ),
        extension_key="hexdemo",
        player_faction="union",
    )
    for a in combat_transitions.follow_up_after_attack(follow_ctx):
        hexdemo_server.action_manager.execute(a)
    st2 = hexdemo_server.action_manager.current_state
    with pytest.raises(ValueError, match="already attacked"):
        att_h = st2.board.units["u_att"].position
        def_h = st2.board.units["u_def"].position
        hexdemo_server.hooks.attack.validate(
            AttackContext(
                state=st2,
                attacker_ids=("u_att",),
                defender_ids=("u_def",),
                attacker_hexes=(att_h,),
                defender_hexes=(def_h,),
                player_faction="union",
                attack_kind="combined",
                params={
                    "attacker_id": "u_att",
                    "attacker_ids": ["u_att"],
                    "defender_id": "u_def",
                    "attack_kind": "combined",
                },
            )
        )


def test_attack_updates_extension_and_rng() -> None:
    st = _hexdemo_combat_state()
    def_hex = st.board.units["u_def"].position
    after = Attack(
        "combined",
        "u_att",
        "u_def",
        outcome="none",
        retreat_distance=None,
        rng_entry={"op": "adjacent_attack", "outcome": "none"},
    ).apply(st)

    from games.hexdemo import combat_transitions
    from hexengine.hooks.attack import AfterAttackAppliedContext, AttackResolution, AttackContext

    att_hex = st.board.units["u_att"].position
    follow_ctx = AfterAttackAppliedContext(
        state=after,
        attack_context=AttackContext(
            state=st,
            attacker_ids=("u_att",),
            defender_ids=("u_def",),
            attacker_hexes=(att_hex,),
            defender_hexes=(def_hex,),
            player_faction="union",
            attack_kind="combined",
            params={"attacker_id": "u_att", "defender_id": "u_def", "attack_kind": "combined"},
        ),
        resolution=AttackResolution(outcome="none"),
        extension_key="hexdemo",
        player_faction="union",
    )
    nxt = after
    for a in combat_transitions.follow_up_after_attack(follow_ctx):
        nxt = a.apply(nxt)

    hx = title_bucket(nxt, "hexdemo")
    assert isinstance(hx, dict)
    assert hx.get("attacks_this_phase") == ["u_att"]
    assert nxt.rng_log[-1]["op"] == "adjacent_attack"
    assert nxt.rng_log[-1]["outcome"] == "none"
    lc = hx.get("last_combat")
    assert isinstance(lc, dict)
    assert lc.get("defender_hex") == {"i": def_hex.i, "j": def_hex.j, "k": def_hex.k}
    assert lc.get("defender_hexes") == [
        {"i": int(def_hex.i), "j": int(def_hex.j), "k": int(def_hex.k)}
    ]
    assert lc.get("attacker_hexes") == [
        {"i": int(att_hex.i), "j": int(att_hex.j), "k": int(att_hex.k)}
    ]


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
        # CRT uses randrange; column 0|1 roll 3 => DC_EX, failed morale => defender RETREAT.
        with patch(
            "games.hexdemo.hooks.attack.random.randrange",
            side_effect=[3, 1],
        ):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "combined",
                    "attacker_id": "u_att",
                    "attacker_ids": ["u_att"],
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
    assert by_pid["p_c"]["retreat_hexes_remaining"] == 1
    assert by_pid["p_u"]["instruction"] == "wait"

    state_msgs = [c for c in captured if c[1] == "state_update"]
    assert state_msgs
    su_by_pid = {pid: payload for pid, _, payload in state_msgs}
    assert su_by_pid["p_u"]["interaction_messages"][-1]["kind"] == "wait"
    assert "Hold" in su_by_pid["p_u"]["interaction_messages"][-1]["text"]
    assert su_by_pid["p_c"]["interaction_messages"][-1]["kind"] == "retreat"
    assert "Mandatory retreat" in su_by_pid["p_c"]["interaction_messages"][-1]["text"]

    assert su_by_pid["p_c"].get("primary_actions") is None
    assert su_by_pid["p_u"].get("primary_actions") is None

    panels_c = su_by_pid["p_c"].get("interaction_panels") or []
    assert len(panels_c) == 1
    assert panels_c[0]["id"] == "turn_actions"
    panel_action_ids = {
        row.get("id") for row in (panels_c[0].get("actions") or []) if isinstance(row, dict)
    }
    assert "combat_disrupt_instead" in panel_action_ids


def test_combat_disrupt_instead_of_retreat(hexdemo_server: GameServer) -> None:
    """Optional CRT retreat: waive mandatory retreat and mark the stack disrupted."""
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
        with patch(
            "games.hexdemo.hooks.attack.random.randrange",
            side_effect=[3, 1],
        ):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "combined",
                    "attacker_id": "u_att",
                    "attacker_ids": ["u_att"],
                    "defender_id": "u_def",
                },
                player_id="p_u",
            )
            await server.handle_message("p_u", req.to_message())

        st = server.action_manager.current_state
        hx = title_bucket(st, "hexdemo")
        assert hx.get("combat_gate") == "awaiting_retreat_or_disrupt"
        ro = hx.get("retreat_obligations", {})
        assert isinstance(ro, dict) and "u_def" in ro

        dreq = ActionRequest(
            action_type="CombatDisruptInsteadOfRetreat",
            params={},
            player_id="p_c",
        )
        await server.handle_message("p_c", dreq.to_message())

        st2 = server.action_manager.current_state
        hx2 = title_bucket(st2, "hexdemo")
        assert not hx2.get("combat_gate")
        assert "u_def" not in (hx2.get("retreat_obligations") or {})
        assert st2.board.units["u_def"].attributes.get("disrupted") is True

    asyncio.run(run())


def test_ranged_artillery_attack_suppresses_attacker_retreat() -> None:
    """CRT attacker retreat is ignored when only artillery participates (ranged bombardment)."""
    gd = game_definition_from_config(default_match_config())
    server = GameServer(
        initial_state=_hexdemo_artillery_ranged_vs_infantry(),
        game_definition=gd,
    )
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.faction_to_player["union"] = "p_u"

    async def run() -> None:
        # Column 0|1, roll 0 => AR (attacker retreat if morale passes); morale roll 1 passes.
        with patch("games.hexdemo.hooks.attack.random.randrange", side_effect=[0, 1]):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "combined",
                    "attacker_id": "u_art",
                    "attacker_ids": ["u_art"],
                    "defender_id": "u_def",
                },
                player_id="p_u",
            )
            await server.handle_message("p_u", req.to_message())

        st = server.action_manager.current_state
        hx = title_bucket(st, "hexdemo")
        lc = hx.get("last_combat")
        assert isinstance(lc, dict)
        assert lc.get("outcome") == "none"
        ro = hx.get("retreat_obligations") or {}
        assert "u_art" not in ro
        entry = st.rng_log[-1]
        assert entry.get("hexdemo_attacker_retreat_suppressed") is True

    asyncio.run(run())


def test_advance_opens_when_wire_primary_is_ranged_but_adjacent_infantry_in_party() -> (
    None
):
    """Advance uses an adjacent stack from `attacker_ids`, not only `attacker_id`."""
    from hexengine.server.protocol import JoinGameRequest

    h_def_orig = Hex(0, 0, 0)
    h_inf = Hex(1, -1, 0)
    h_art = Hex(2, -2, 0)
    h_ret = next(h for h in neighbors(h_def_orig) if h != h_inf)
    board = BoardState(
        units={
            "u_art": UnitState(
                unit_id="u_art",
                unit_type="artillery",
                faction="union",
                position=h_art,
                health=100,
                active=True,
                attributes={"combat": 5, "morale": 6, "range": 4},
            ),
            "u_inf": UnitState(
                unit_id="u_inf",
                unit_type="infantry",
                faction="union",
                position=h_inf,
                health=100,
                active=True,
                attributes={"combat": 5, "morale": 4},
            ),
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="infantry",
                faction="confederate",
                position=h_ret,
                health=100,
                active=True,
                attributes={"combat": 4, "morale": 4},
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
    hx = {
        "last_combat": {
            "attack_kind": "combined",
            "outcome": "defender_retreat",
            "attacker_id": "u_art",
            "attacker_ids": ["u_art", "u_inf"],
            "defender_id": "u_def",
            "defender_ids": ["u_def"],
            "defender_hex": {"i": h_def_orig.i, "j": h_def_orig.j, "k": h_def_orig.k},
            "defender_hexes": [
                {"i": h_def_orig.i, "j": h_def_orig.j, "k": h_def_orig.k}
            ],
            "attacker_hexes": [
                {"i": h_art.i, "j": h_art.j, "k": h_art.k},
                {"i": h_inf.i, "j": h_inf.j, "k": h_inf.k},
            ],
            "retreat_distance": 1,
            "retreat_unit_id": "u_def",
        },
        "retreat_obligations": {},
    }
    st = GameState(board=board, turn=turn, title_state=hx, title_bucket_key="hexdemo", rng_log=())
    gd = game_definition_from_config(default_match_config())
    server = GameServer(initial_state=st, game_definition=gd)

    async def run() -> None:
        await server.handle_message(
            "p_u", JoinGameRequest(player_name="U", faction="union").to_message()
        )
        server._maybe_open_combat_advance_after_retreat("hexdemo")
        st2 = server.action_manager.current_state
        adv = title_bucket(st2, "hexdemo").get("advance")
        assert isinstance(adv, dict)
        assert adv.get("faction") == "union"
        assert adv.get("unit_ids") == ["u_inf"]
        assert adv.get("to_hex") == {
            "i": h_def_orig.i,
            "j": h_def_orig.j,
            "k": h_def_orig.k,
        }

    asyncio.run(run())


def test_combat_advance_after_defender_retreat(hexdemo_server: GameServer) -> None:
    """After defender fulfills retreat, attacker may advance into vacated defender hex."""
    from hexengine.server.protocol import JoinGameRequest

    server = hexdemo_server
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.players["p_c"] = PlayerInfo(
        player_id="p_c", player_name="C", faction="confederate", connected=True
    )
    server.faction_to_player["union"] = "p_u"
    server.faction_to_player["confederate"] = "p_c"

    st0 = server.action_manager.current_state
    h_att = st0.board.units["u_att"].position
    h_def = st0.board.units["u_def"].position
    # Pick a retreat destination adjacent to defender but not attacker.
    h_ret = next(h for h in neighbors(h_def) if h != h_att)

    async def run() -> None:
        await server.handle_message(
            "p_u", JoinGameRequest(player_name="U", faction="union").to_message()
        )
        await server.handle_message(
            "p_c", JoinGameRequest(player_name="C", faction="confederate").to_message()
        )

        # Defender retreat: CRT roll 3 on column 0|1 => DC_EX, failed morale => defender RETREAT.
        with patch("games.hexdemo.hooks.attack.random.randrange", side_effect=[3, 1]):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "combined",
                    "attacker_id": "u_att",
                    "attacker_ids": ["u_att"],
                    "defender_id": "u_def",
                },
                player_id="p_u",
            )
            await server.handle_message("p_u", req.to_message())

        # Defender fulfills the (1-hex) retreat.
        mv = ActionRequest(
            action_type="MoveUnit",
            params={
                "unit_id": "u_def",
                "from_hex": {"i": h_def.i, "j": h_def.j, "k": h_def.k},
                "to_hex": {"i": h_ret.i, "j": h_ret.j, "k": h_ret.k},
            },
            player_id="p_c",
        )
        await server.handle_message("p_c", mv.to_message())

        st1 = server.action_manager.current_state
        hx = title_bucket(st1, "hexdemo")
        assert hx.get("combat_gate") == "awaiting_advance"
        adv = hx.get("advance")
        assert isinstance(adv, dict)
        assert adv.get("faction") == "union"

        panels_u = server._interaction_panels_for_player_id("p_u")
        assert panels_u is not None and len(panels_u) == 1
        assert panels_u[0]["id"] == "turn_actions"
        assert panels_u[0]["dock_arc"] == "advance_gate"
        action_ids = {a["id"] for a in panels_u[0].get("actions") or []}
        assert "combat_advance" in action_ids

        # Attacker advances into the vacated defender hex.
        adv_req = ActionRequest(
            action_type="CombatAdvance",
            params={},
            player_id="p_u",
        )
        await server.handle_message("p_u", adv_req.to_message())

        st2 = server.action_manager.current_state
        assert st2.board.units["u_att"].position == h_def
        hx2 = title_bucket(st2, "hexdemo")
        assert hx2.get("combat_gate") is None
        assert hx2.get("advance") is None

    asyncio.run(run())


def test_combat_advance_via_move_unit_optional_path(hexdemo_server: GameServer) -> None:
    """Player may also advance by issuing a MoveUnit into the vacated defender hex."""
    from hexengine.server.protocol import JoinGameRequest

    server = hexdemo_server
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.players["p_c"] = PlayerInfo(
        player_id="p_c", player_name="C", faction="confederate", connected=True
    )
    server.faction_to_player["union"] = "p_u"
    server.faction_to_player["confederate"] = "p_c"

    st0 = server.action_manager.current_state
    h_att = st0.board.units["u_att"].position
    h_def = st0.board.units["u_def"].position
    h_ret = next(h for h in neighbors(h_def) if h != h_att)

    async def run() -> None:
        await server.handle_message(
            "p_u", JoinGameRequest(player_name="U", faction="union").to_message()
        )
        await server.handle_message(
            "p_c", JoinGameRequest(player_name="C", faction="confederate").to_message()
        )

        with patch("games.hexdemo.hooks.attack.random.randrange", side_effect=[3, 1]):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "combined",
                    "attacker_id": "u_att",
                    "attacker_ids": ["u_att"],
                    "defender_id": "u_def",
                },
                player_id="p_u",
            )
            await server.handle_message("p_u", req.to_message())

        mv = ActionRequest(
            action_type="MoveUnit",
            params={
                "unit_id": "u_def",
                "from_hex": {"i": h_def.i, "j": h_def.j, "k": h_def.k},
                "to_hex": {"i": h_ret.i, "j": h_ret.j, "k": h_ret.k},
            },
            player_id="p_c",
        )
        await server.handle_message("p_c", mv.to_message())

        st1 = server.action_manager.current_state
        hx = title_bucket(st1, "hexdemo")
        assert hx.get("combat_gate") == "awaiting_advance"

        # Advance by MoveUnit into the vacated defender hex.
        adv_move = ActionRequest(
            action_type="MoveUnit",
            params={
                "unit_id": "u_att",
                "from_hex": {"i": h_att.i, "j": h_att.j, "k": h_att.k},
                "to_hex": {"i": h_def.i, "j": h_def.j, "k": h_def.k},
            },
            player_id="p_u",
        )
        await server.handle_message("p_u", adv_move.to_message())

        st2 = server.action_manager.current_state
        assert st2.board.units["u_att"].position == h_def
        hx2 = title_bucket(st2, "hexdemo")
        assert hx2.get("combat_gate") is None
        assert hx2.get("advance") is None

    asyncio.run(run())


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
                "attack_kind": "combined",
                "attacker_id": "u_att",
                "attacker_ids": ["u_att"],
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

    from hexengine.state.title_extension import title_bucket

    hx = dict(title_bucket(st, "hexdemo"))
    hx["retreat_obligations"] = {"u_att": 2}
    hx["combat_gate"] = "awaiting_retreat"
    server.action_manager.replace_state(
        st.with_title_state(hx, title_bucket_key="hexdemo")
    )

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
    ro = title_bucket(after, "hexdemo").get("retreat_obligations", {})
    assert "u_att" not in ro


def test_clear_hexdemo_combat_on_next_phase(hexdemo_server: GameServer) -> None:
    server = hexdemo_server
    from games.hexdemo import combat_transitions
    from hexengine.hooks.attack import AfterAttackAppliedContext, AttackResolution, AttackContext

    before = server.action_manager.current_state
    att_hex = before.board.units["u_att"].position
    def_hex = before.board.units["u_def"].position
    server.action_manager.execute(
        Attack(
            "adjacent",
            "u_att",
            "u_def",
            outcome="none",
            retreat_distance=None,
            rng_entry={"op": "adjacent_attack", "outcome": "none"},
        )
    )
    after = server.action_manager.current_state
    follow_ctx = AfterAttackAppliedContext(
        state=after,
        attack_context=AttackContext(
            state=before,
            attacker_ids=("u_att",),
            defender_ids=("u_def",),
            attacker_hexes=(att_hex,),
            defender_hexes=(def_hex,),
            player_faction="union",
            attack_kind="adjacent",
            params={"attacker_id": "u_att", "defender_id": "u_def", "attack_kind": "adjacent"},
        ),
        resolution=AttackResolution(outcome="none"),
        extension_key="hexdemo",
        player_faction="union",
    )
    for a in combat_transitions.follow_up_after_attack(follow_ctx):
        server.action_manager.execute(a)
    from hexengine.state.title_extension import title_bucket as tb

    assert tb(server.action_manager.current_state, "hexdemo").get(
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
    hx = tb(server.action_manager.current_state, "hexdemo")
    assert "attacks_this_phase" not in hx
    assert "last_combat" not in hx


def test_auto_advance_when_sole_attacker_has_attacked(
    hexdemo_server: GameServer,
) -> None:
    server = hexdemo_server
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.faction_to_player["union"] = "p_u"

    async def run() -> None:
        # Roll 0 on column 0|1 => AR; failed morale with no "failed" CRT cell => no effect.
        with patch(
            "games.hexdemo.hooks.attack.random.randrange",
            side_effect=[0, 1],
        ):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "combined",
                    "attacker_id": "u_att",
                    "attacker_ids": ["u_att"],
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
        with patch(
            "games.hexdemo.hooks.attack.random.randrange",
            side_effect=[3, 1],
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
    server = GameServer(
        initial_state=_hexdemo_two_union_vs_one_def(), game_definition=gd
    )
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.faction_to_player["union"] = "p_u"

    async def attack(attacker: str) -> None:
        with patch(
            "games.hexdemo.hooks.attack.random.randrange",
            side_effect=[0, 1],
        ):
            req = ActionRequest(
                action_type="Attack",
                params={
                    "attack_kind": "combined",
                    "attacker_id": attacker,
                    "attacker_ids": [attacker],
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
