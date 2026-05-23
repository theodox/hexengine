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
from ...state import ActionManager, GameState
from ...state.actions import (
    ClearUnitRetreatObligation,
    MoveUnit,
    ResolveCombatAdvance,
    ResolveDisruptInsteadOfRetreat,
)
from ..protocol import ActionRequest, ActionResult, Message, PlayerInfo


class AuthorityCombatCleanupHost(Protocol):
    """Minimal `GameServer` surface for combat cleanup actions."""

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

    def _maybe_open_combat_advance_after_retreat(self, extension_key: str) -> None: ...


async def _reply_ok_broadcast(host: AuthorityCombatCleanupHost, player_id: str) -> None:
    result = ActionResult(success=True, action_id=str(uuid.uuid4()))
    await host._send_message(player_id, result.to_message())
    await host._broadcast_state_update()


def move_unit_is_combat_advance_fulfillment(
    state: GameState,
    params: dict[str, Any],
    *,
    player_faction: str,
    extension_key: str | None,
) -> bool:
    """
    True when this `MoveUnit` wire is the title-declared advance into the vacated hex
    (extension `combat_gate` awaiting_advance).
    """

    if not extension_key:
        return False
    hx_adv = state.extension.get(extension_key)
    if not isinstance(hx_adv, dict):
        return False
    if str(hx_adv.get("combat_gate", "")).strip() != "awaiting_advance":
        return False
    adv = hx_adv.get("advance")
    if not isinstance(adv, dict) or str(adv.get("faction", "")).strip() != str(
        player_faction
    ):
        return False
    to_hex_raw = adv.get("to_hex")
    unit_ids_raw = adv.get("unit_ids")
    if not (
        isinstance(to_hex_raw, dict)
        and isinstance(unit_ids_raw, list)
        and isinstance(params.get("unit_id"), str)
        and isinstance(params.get("to_hex"), dict)
    ):
        return False
    try:
        adv_to = Hex(
            int(to_hex_raw["i"]),
            int(to_hex_raw["j"]),
            int(to_hex_raw["k"]),
        )
    except Exception:
        return False
    try:
        req_to = Hex(**params["to_hex"])
    except Exception:
        return False
    uid = str(params["unit_id"]).strip()
    allowed_ids = {str(x) for x in unit_ids_raw if isinstance(x, str)}
    return bool(uid and req_to == adv_to and uid in allowed_ids)


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
    hx0 = st0.extension.get(ek)
    if (
        not isinstance(hx0, dict)
        or str(hx0.get("combat_gate", "")).strip() != "awaiting_retreat_or_disrupt"
    ):
        await host._send_error(
            player_id, "Cannot take disruption instead of retreat right now"
        )
        return
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
        host.action_manager.execute(
            ResolveDisruptInsteadOfRetreat(ek, str(player.faction))
        )
    except Exception as e:
        await host._send_error(player_id, f"Action failed: {e}")
        return
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
    st0 = host.action_manager.current_state
    hx0 = st0.extension.get(ek)
    if (
        not isinstance(hx0, dict)
        or str(hx0.get("combat_gate", "")).strip() != "awaiting_advance"
    ):
        await host._send_error(player_id, "No combat advance is pending right now")
        return
    adv = hx0.get("advance")
    if not isinstance(adv, dict) or str(adv.get("faction", "")).strip() != str(
        player.faction
    ):
        await host._send_error(player_id, "You are not allowed to advance right now")
        return
    try:
        host.action_manager.execute(ResolveCombatAdvance(ek, str(player.faction)))
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
        to_move = [uid_for_move]
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
    """Run `ResolveCombatAdvance` when advance is fulfilled by a `MoveUnit` into the hex."""

    ek = host._title_extension_key()
    if not ek:
        await host._send_error(
            player_id,
            "This game title does not define a state extension key for combat",
        )
        return
    try:
        host.action_manager.execute(ResolveCombatAdvance(ek, str(player.faction)))
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
        host._maybe_open_combat_advance_after_retreat(r_ek)


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
