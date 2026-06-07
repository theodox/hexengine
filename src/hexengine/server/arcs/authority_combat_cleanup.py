"""
Authority-side **combat cleanup** arc: disruption instead of retreat, combat advance,
advance resolution via `MoveUnit`, and stacked retreat fulfillment.

The primary `Attack` pipeline lives in `hexengine.server.arcs.authority_attack`. Stepwise
movement lives in `authority_movement`.

See **Arc** / **Segment** vocabulary in `hexengine.state.movement_arc`.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from ...hexes.types import Hex
from ...hooks.attack import CombatAdvanceMoveContext, CombatCleanupContext
from ...hooks.core import ENGINE_DEFAULT
from ...hooks.title import TitleHooks
from ...state import ActionManager, GameState
from ...state.action_manager import StateAction
from ...state.actions import ClearUnitRetreatObligation, MoveUnit
from ..protocol import ActionRequest, ActionResult, Message, PlayerInfo


def _execute_hook_state_actions(
    host: AuthorityCombatCleanupHost,
    raw: list[StateAction] | object,
    *,
    hook_name: str,
) -> None:
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


class AuthorityCombatCleanupHost(Protocol):
    """Minimal `GameServer` surface for combat cleanup actions."""

    hooks: TitleHooks
    action_manager: ActionManager

    def _title_extension_key(self) -> str | None: ...

    async def _send_error(self, player_id: str, message: str) -> None: ...

    async def _send_message(self, player_id: str, message: Message) -> None: ...

    async def _broadcast_state_update(self) -> None: ...

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

    def _on_retreat_obligation_cleared(
        self, extension_key: str, *, cleared_unit_ids: tuple[str, ...] = ()
    ) -> None: ...


async def _reply_ok_broadcast(host: AuthorityCombatCleanupHost, player_id: str) -> None:
    result = ActionResult(success=True, action_id=str(uuid.uuid4()))
    await host._send_message(player_id, result.to_message())
    await host._broadcast_state_update()


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


async def handle_combat_disrupt_instead_of_retreat(
    host: AuthorityCombatCleanupHost,
    player_id: str,
    player: PlayerInfo,
) -> None:
    ek = host._title_extension_key()
    if not ek:
        await host._send_error(
            player_id,
            "This game title does not define a state extension key for combat",
        )
        return
    st0 = host.action_manager.current_state
    from ...state.title_extension import title_bucket

    hx0 = title_bucket(st0, ek)
    ro0 = hx0.get("retreat_obligations")
    ro0 = ro0 if isinstance(ro0, dict) else {}
    has_ob = False
    for uid, raw in ro0.items():
        try:
            if int(raw) <= 0:
                continue
        except (TypeError, ValueError):
            continue
        u = st0.board.units.get(str(uid))
        if u is not None and u.active and u.faction == player.faction:
            has_ob = True
            break
    if not has_ob:
        await host._send_error(
            player_id, "No mandatory retreat to waive for your units"
        )
        return
    try:
        cleanup_ctx = CombatCleanupContext(
            state=st0,
            extension_key=ek,
            player_faction=str(player.faction),
        )
        raw = host.hooks.attack.disrupt_instead_of_retreat(cleanup_ctx)
        _execute_hook_state_actions(
            host,
            raw,
            hook_name="hooks.attack.combat_disrupt_instead_of_retreat",
        )
    except Exception as e:
        await host._send_error(player_id, f"Action failed: {e}")
        return
    host._on_retreat_obligation_cleared(ek)
    await _reply_ok_broadcast(host, player_id)


async def handle_combat_advance_rpc(
    host: AuthorityCombatCleanupHost,
    player_id: str,
    player: PlayerInfo,
) -> None:
    ek = host._title_extension_key()
    if not ek:
        await host._send_error(
            player_id,
            "This game title does not define a state extension key for combat",
        )
        return
    from ...state.title_extension import title_bucket

    st0 = host.action_manager.current_state
    try:
        cleanup_ctx = CombatCleanupContext(
            state=st0,
            extension_key=ek,
            player_faction=str(player.faction),
        )
        raw = host.hooks.attack.resolve_combat_advance(cleanup_ctx)
        _execute_hook_state_actions(
            host,
            raw,
            hook_name="hooks.attack.combat_resolve_advance",
        )
    except Exception as e:
        await host._send_error(player_id, f"Action failed: {e}")
        return
    await _reply_ok_broadcast(host, player_id)


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
    Validate the full stacked retreat before any `MoveUnit` executes.

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


async def handle_move_unit_combat_advance_resolution(
    host: AuthorityCombatCleanupHost,
    player_id: str,
    player: PlayerInfo,
) -> None:
    """Run title combat advance resolution when advance is fulfilled by `MoveUnit`."""

    ek = host._title_extension_key()
    if not ek:
        await host._send_error(
            player_id,
            "This game title does not define a state extension key for combat",
        )
        return
    st0 = host.action_manager.current_state
    try:
        cleanup_ctx = CombatCleanupContext(
            state=st0,
            extension_key=ek,
            player_faction=str(player.faction),
        )
        raw = host.hooks.attack.resolve_combat_advance(cleanup_ctx)
        _execute_hook_state_actions(
            host,
            raw,
            hook_name="hooks.attack.combat_resolve_advance",
        )
    except Exception as e:
        await host._send_error(player_id, f"Action failed: {e}")
        return
    await _reply_ok_broadcast(host, player_id)


def finalize_retreat_fulfillment_stack(
    host: AuthorityCombatCleanupHost,
    *,
    uid_for_move: str,
    player: PlayerInfo,
    request: ActionRequest,
    st_before: GameState,
) -> None:
    """
    After the primary `MoveUnit` for retreat executes, move stackmates and clear
    retreat obligations.

    Args:
        host: Game server.
        uid_for_move: Requested unit id (already moved by the primary action).
        player: Acting player.
        request: Original `MoveUnit` request.
        st_before: State snapshot from before the primary `execute` (for stack detection).
    """

    r_ek = host._title_extension_key()
    fh, th = request.params.get("from_hex"), request.params.get("to_hex")
    if isinstance(fh, dict) and isinstance(th, dict):
        from_hex = Hex(**fh)
        to_hex = Hex(**th)
    else:
        from_hex = None
        to_hex = None
    to_move: list[str] = []
    if from_hex is not None and to_hex is not None:
        to_move = retreat_stack_unit_ids(
            host, st_before, from_hex, player, uid_for_move
        )
        for other_uid in to_move:
            if other_uid == uid_for_move:
                continue
            host.action_manager.execute(
                MoveUnit(other_uid, from_hex=from_hex, to_hex=to_hex)
            )
    if r_ek:
        for moved_uid in to_move:
            host.action_manager.execute(ClearUnitRetreatObligation(moved_uid, r_ek))
        host._on_retreat_obligation_cleared(r_ek, cleared_unit_ids=tuple(to_move))


__all__ = [
    "AuthorityCombatCleanupHost",
    "finalize_retreat_fulfillment_stack",
    "handle_combat_advance_rpc",
    "handle_combat_disrupt_instead_of_retreat",
    "handle_move_unit_combat_advance_resolution",
    "move_unit_is_combat_advance_fulfillment",
    "retreat_stack_unit_ids",
    "validate_retreat_fulfillment_stack",
]
