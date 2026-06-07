"""
Combat cleanup helpers for the arc runtime.

Dedicated combat RPCs (disrupt, advance, retreat fulfillment) are handled only through
the declared combat arc (`try_combat_arc_rpc`, `try_combat_arc_move_unit`). This module
keeps advance-move detection and stacked-retreat pre-validation used before the arc runs.
"""

from __future__ import annotations

from typing import Any, Protocol

from ...hexes.types import Hex
from ...hooks.attack import CombatAdvanceMoveContext
from ...hooks.core import ENGINE_DEFAULT
from ...hooks.title import TitleHooks
from ...hooks.core import ENGINE_DEFAULT
from ...state import ActionManager, GameState
from ...state.action_manager import StateAction
from ..protocol import ActionRequest, PlayerInfo


class AuthorityCombatCleanupHost(Protocol):
    """Minimal `GameServer` surface for combat cleanup prechecks."""

    hooks: TitleHooks
    action_manager: ActionManager

    def _validate_move_unit_request(
        self,
        state: GameState,
        params: dict[str, Any],
        player: PlayerInfo,
        *,
        is_retreat_fulfillment: bool = False,
    ) -> None: ...

    def _retreat_obligation_hexes_remaining(
        self, state: GameState, unit_id: str
    ) -> int | None: ...

    def _max_active_units_per_hex(
        self, state: GameState, unit_id: str
    ) -> int | None: ...


def execute_hook_state_actions(
    host: AuthorityCombatCleanupHost,
    raw: list[StateAction] | object,
    *,
    hook_name: str,
) -> None:
    """Apply title hook ``StateAction`` list on the authoritative action manager."""

    if raw is ENGINE_DEFAULT:
        raise ValueError(f"This game title does not implement {hook_name}")
    if not isinstance(raw, list):
        raise TypeError(
            f"{hook_name} must return list[StateAction] or hooks.ENGINE_DEFAULT"
        )
    for action in raw:
        if not isinstance(action, StateAction):
            raise TypeError(f"{hook_name} entries must be StateAction instances")
        host.action_manager.execute(action)


def move_unit_is_combat_advance_fulfillment(
    hooks: TitleHooks,
    state: GameState,
    params: dict[str, Any],
    *,
    player_faction: str,
    extension_key: str | None,
) -> bool:
    """
    True when this `MoveUnit` wire is the title-declared advance into the vacated hex.

    The decision is title policy (`AttackHook.IS_COMBAT_ADVANCE_MOVE`); the engine has
    no default and treats `ENGINE_DEFAULT` as "not an advance move".
    """

    if not extension_key:
        return False
    ctx = CombatAdvanceMoveContext(
        state=state,
        params=dict(params),
        extension_key=extension_key,
        player_faction=str(player_faction),
    )
    raw = hooks.attack.detect_combat_advance_move(ctx)
    if raw is ENGINE_DEFAULT:
        return False
    return bool(raw)


def retreat_stack_unit_ids(
    host: AuthorityCombatCleanupHost,
    st_before: GameState,
    from_hex: Hex,
    player: PlayerInfo,
    uid_for_move: str,
) -> list[str]:
    """Unit ids that must retreat together from `from_hex` (includes `uid_for_move`)."""

    to_move: list[str] = []
    for u in st_before.board.active_units_at_hex(from_hex):
        if u.faction != player.faction:
            continue
        if host._retreat_obligation_hexes_remaining(st_before, u.unit_id) is None:
            continue
        to_move.append(u.unit_id)
    if uid_for_move not in to_move:
        to_move.append(uid_for_move)
    return to_move


def validate_retreat_fulfillment_stack(
    host: AuthorityCombatCleanupHost,
    *,
    st_before: GameState,
    uid_for_move: str,
    player: PlayerInfo,
    request: ActionRequest,
) -> None:
    """
    Validate the full stacked retreat before the combat arc applies the move.

    Without this, the primary unit can move and stackmate validation can fail later,
    leaving server state ahead of clients (no broadcast) and causing stale `from_hex`
    on the next drag.
    """

    fh, th = request.params.get("from_hex"), request.params.get("to_hex")
    if not isinstance(fh, dict) or not isinstance(th, dict):
        raise ValueError("MoveUnit requires from_hex and to_hex")
    from_hex = Hex(**fh)
    to_hex = Hex(**th)
    to_move = retreat_stack_unit_ids(
        host, st_before, from_hex, player, uid_for_move
    )
    for uid in to_move:
        host._validate_move_unit_request(
            st_before,
            {
                "unit_id": uid,
                "from_hex": fh,
                "to_hex": th,
            },
            player,
            is_retreat_fulfillment=True,
        )
    max_stack = host._max_active_units_per_hex(st_before, uid_for_move)
    if max_stack is not None:
        dest_count = len(st_before.board.active_units_at_hex(to_hex))
        if dest_count + len(to_move) > max_stack:
            raise ValueError(
                f"Destination hex already has {dest_count} active units; "
                f"cannot retreat {len(to_move)} more (stacking limit {max_stack})"
            )


__all__ = [
    "AuthorityCombatCleanupHost",
    "execute_hook_state_actions",
    "move_unit_is_combat_advance_fulfillment",
    "retreat_stack_unit_ids",
    "validate_retreat_fulfillment_stack",
]
