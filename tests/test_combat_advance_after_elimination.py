"""Regression: advance gate must block auto phase advance after elimination."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from hexengine.server.game_server import GameServer
from hexengine.server.protocol import ActionRequest, JoinGameRequest, PlayerInfo
from hexengine.state.title_extension import title_bucket

from games.hexdemo import combat_transitions
from games.hexdemo.hooks import attack as attack_hooks
from tests.test_combat_hexdemo import _hexdemo_combat_state, hexdemo_server


def test_auto_advance_blocked_while_awaiting_advance_gate() -> None:
    st = _hexdemo_combat_state().with_title_state(
        {
            "combat_gate": combat_transitions.GATE_AWAITING_ADVANCE,
            "attacks_this_phase": ["u_att"],
        },
        title_bucket_key="hexdemo",
    )
    assert attack_hooks.auto_advance_phase_after_attack(st) is False


def test_attack_eliminating_defender_offers_advance_not_auto_phase(
    hexdemo_server: GameServer,
) -> None:
    """Second step loss on EXCHANGE deletes the defender; advance gate must appear."""

    server = hexdemo_server
    st0 = server.action_manager.current_state
    u_def = st0.board.units["u_def"]
    server.action_manager.replace_state(
        st0.with_board(
            st0.board.with_unit(
                u_def.with_attributes(
                    {**u_def.attributes, "steps_lost": 1, "morale": 4}
                )
            )
        )
    )
    server.players["p_u"] = PlayerInfo(
        player_id="p_u", player_name="U", faction="union", connected=True
    )
    server.faction_to_player["union"] = "p_u"

    async def run() -> None:
        await server.handle_message(
            "p_u", JoinGameRequest(player_name="U", faction="union").to_message()
        )
        # Column 0|1, roll 3 => DC_EX => EXCHANGE when defender morale passes (roll 4).
        with patch(
            "games.hexdemo.hooks.attack.random.randrange",
            side_effect=[3, 4],
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
    assert st.turn.current_phase == "Combat"
    assert st.turn.current_faction == "union"
    hx = title_bucket(st, "hexdemo")
    assert hx.get("combat_gate") == combat_transitions.GATE_AWAITING_ADVANCE
    adv = hx.get("advance")
    assert isinstance(adv, dict)
    assert adv.get("faction") == "union"
    assert not st.board.units["u_def"].active
