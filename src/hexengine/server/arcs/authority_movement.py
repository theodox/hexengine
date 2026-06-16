"""
Authority-side **movement arc**: stepwise `MoveUnit`, interrupt handoff, and continuation.

See **Arc** / **Segment** vocabulary in `hexengine.state.movement_arc`. Attack and combat
cleanup arcs live in `hexengine.server.arcs.authority_attack` and `authority_combat_cleanup`.

**Stepwise open vs continuation:** see ``movement_arc_decl`` for why mandatory retreats
reuse this arc. Multi-hex retreats: title validation here, then
``drive_movement_arc_retreat_open``. Normal ``resolve_move_as_steps`` still opens inline.
Continuation: ``drive_movement_arc_event`` / ``continue_stepwise_move_unit``. Opt-in:
``ArcHook.MOVEMENT_ARC`` → ``ENGINE_MOVEMENT_ARC_PRESET`` or custom ``ArcSpec``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any, Protocol

from ...arcs import ArcContext, read_arc_cursor
from ...arcs.movement_arc_decl import MOVEMENT_ARC_ID, path_complete
from ...hexes.types import Hex
from ...hooks.core import ENGINE_DEFAULT
from ...hooks.modification import MoveContext, MovementStepContext
from ...hooks.title import TitleHooks
from ...retreat_path import parse_wire_path, validate_retreat_path
from ...state import ActionManager, GameState
from ...state.engine_session_state import engine_bucket
from ...state.actions import MoveUnit, SetTurnState, WriteHexengineMovementArc
from ...state.logic import is_valid_move, shortest_move_path
from ...state.movement_arc import (
    HEXENGINE_MOVEMENT_ARC_KEY,
    MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
    MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
    MOVEMENT_ARC_SCHEMA,
    MOVEMENT_INTERRUPT_PHASE,
    turn_state_to_movement_arc_snapshot,
)
from ..protocol import ActionRequest, Message, PlayerInfo
from .authority_arc_runtime import (
    COMBAT_ARC_REQUIRED_MSG,
    ArcDispatch,
    drive_movement_arc_event,
    drive_movement_arc_retreat_open,
    finish_arc_dispatch,
    resume_combat_arc_after_retreat_fulfillment,
    sync_movement_cursor_from_payload,
    try_arc_move_unit,
)
from .authority_combat_cleanup import validate_retreat_fulfillment_stack


def dedupe_faction_ids(items: tuple[str, ...]) -> tuple[str, ...]:
    """Stable de-dupe for faction id tuples (movement interrupt queue)."""

    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return tuple(out)


def read_movement_arc(state: GameState) -> dict[str, Any] | None:
    """Return movement **arc** payload in `extension`, if any."""

    raw = engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY)
    return raw if raw else None


def retreat_path_wire_deferred_to_movement_arc(params: dict[str, Any]) -> bool:
    """True when ``MoveUnit`` carries a retreat ``path`` wire for the movement arc."""

    wire_path = params.get("path")
    return isinstance(wire_path, list) and len(wire_path) >= 2


def retreat_finalize_request_from_params(
    params: dict[str, Any], unit_id: str
) -> dict[str, Any] | None:
    """Build combat fulfillment params from a retreat ``path`` wire (endpoint move)."""

    path = parse_wire_path(params.get("path"))
    if len(path) < 2:
        return None
    wire_path = [{"i": int(h.i), "j": int(h.j), "k": int(h.k)} for h in path]
    return {
        "unit_id": unit_id,
        "from_hex": wire_path[0],
        "to_hex": wire_path[-1],
    }


def _retreat_movement_already_fulfilled(
    host: AuthorityMovementHost, fin_params: dict[str, Any]
) -> bool:
    """True when the movement arc already placed the retreat stack on the path endpoint."""

    uid = fin_params.get("unit_id")
    th = fin_params.get("to_hex")
    if not isinstance(uid, str) or not isinstance(th, dict):
        return False
    try:
        to_hex = Hex(int(th["i"]), int(th["j"]), int(th["k"]))
    except (KeyError, TypeError, ValueError):
        return False
    unit = host.action_manager.current_state.board.units.get(uid.strip())
    return unit is not None and unit.position == to_hex


def _retreat_fulfillment_actions_from_binding(
    host: AuthorityMovementHost,
    player: PlayerInfo,
    fin_params: dict[str, Any],
) -> list[Any] | None:
    """Title combat binding actions to clear obligations after the movement arc finishes."""

    binding = host.hooks.arcs.combat_rules_binding_spec()
    if binding is ENGINE_DEFAULT:
        return None
    apply_fn = getattr(binding, "apply_retreat_step", None)
    if not callable(apply_fn):
        return None
    ctx = ArcContext(
        state=host.action_manager.current_state,
        session_state_key=host.action_manager.current_state.session_state_key,
        owner_faction=str(player.faction),
        params=dict(fin_params),
    )
    return apply_fn(ctx)


def path_tuple_from_movement_arc(arc: dict[str, Any]) -> tuple[Hex, ...]:
    """Parse `path` wire list from a movement arc payload into `Hex` tuples."""

    raw = arc.get("path")
    if not isinstance(raw, list):
        return ()
    out: list[Hex] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            out.append(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(out)


class AuthorityMovementHost(Protocol):
    """Minimal `GameServer` surface for movement arc orchestration."""

    action_manager: ActionManager
    hooks: TitleHooks
    logger: logging.Logger

    async def _send_error(self, player_id: str, message: str) -> None: ...

    async def _send_message(self, player_id: str, message: Message) -> None: ...

    async def _broadcast_state_update(self) -> None: ...

    async def _send_move_unit_success_and_broadcast(self, player_id: str) -> None: ...

    def _validate_move_unit_request(
        self,
        state: GameState,
        params: dict[str, Any],
        player: PlayerInfo,
        *,
        is_retreat_fulfillment: bool = False,
    ) -> None: ...

    def _max_active_units_per_hex(
        self, state: GameState, unit_id: str
    ) -> int | None: ...

    def _zoc_hexes_for_unit(
        self, state: GameState, unit_id: str
    ) -> frozenset[Hex] | None: ...

    def _movement_step_cost_fn(
        self, unit_id: str
    ) -> Callable[[GameState, Hex, Hex, float], float] | None: ...

    def _movement_budget_for_unit(self, state: GameState, unit_id: str) -> float: ...

    def _movement_step_total_cost(
        self, state: GameState, unit_id: str, from_h: Hex, to_h: Hex
    ) -> float: ...

    def _spend_action_after_normal_move_unit(self) -> None: ...


async def _complete_retreat_fulfillment_step(
    host: AuthorityMovementHost,
    player_id: str,
    player: PlayerInfo,
    *,
    fin_params: dict[str, Any],
) -> bool:
    """
    Finish a stepwise retreat through the combat arc when declared.

    When the movement arc already applied the move (combat overlay cursor inactive),
    fall back to the title ``COMBAT_RULES_BINDING.apply_retreat_step``.

    Returns True when the RPC is fully handled (arc success or error).
    """

    outcome = await try_arc_move_unit(
        host,
        player_id,
        player,
        fin_params,
        is_retreat_fulfillment=True,
        is_advance_fulfillment=False,
    )
    if outcome == ArcDispatch.REJECTED and _retreat_movement_already_fulfilled(
        host, fin_params
    ):
        outcome = ArcDispatch.NO_CURSOR
    if outcome == ArcDispatch.HANDLED:
        await finish_arc_dispatch(host, player_id, outcome)
        return True
    if outcome in (ArcDispatch.NO_CURSOR, ArcDispatch.NOT_DECLARED):
        actions = _retreat_fulfillment_actions_from_binding(host, player, fin_params)
        if actions is not None:
            try:
                for action in actions:
                    host.action_manager.execute(action)
            except Exception as e:
                await host._send_error(player_id, str(e))
                return True
            resume_combat_arc_after_retreat_fulfillment(host)
            await host._broadcast_state_update()
            return True
    if outcome == ArcDispatch.NOT_DECLARED:
        await host._send_error(player_id, COMBAT_ARC_REQUIRED_MSG)
        return True
    await finish_arc_dispatch(host, player_id, outcome)
    return True


async def continue_stepwise_move_unit(
    host: AuthorityMovementHost,
    player_id: str,
    player: PlayerInfo,
    request: ActionRequest,
    current_state: GameState,
    flow: dict[str, Any],
) -> bool:
    """Apply the next segment of an in-progress stepwise path. Returns True when handled."""

    if str(flow.get("moving_faction", "")) != str(player.faction):
        await host._send_error(player_id, "Not your stepwise move to continue")
        return True
    unit_id = str(flow.get("unit_id", "")).strip()
    path = path_tuple_from_movement_arc(flow)
    if not unit_id or len(path) < 2:
        await host._send_error(player_id, "Invalid movement arc")
        return True
    idx = int(flow.get("step_index", -1))
    if idx < 0 or idx >= len(path) - 1:
        await host._send_error(player_id, "Invalid movement arc step")
        return True

    fh, th = request.params.get("from_hex"), request.params.get("to_hex")
    if not isinstance(fh, dict) or not isinstance(th, dict):
        await host._send_error(player_id, "MoveUnit requires from_hex and to_hex")
        return True
    from_hex = Hex(**fh)
    to_hex = Hex(**th)
    if from_hex != path[idx] or to_hex != path[idx + 1]:
        await host._send_error(
            player_id, "MoveUnit does not match the committed stepwise path"
        )
        return True

    unit = current_state.board.units.get(unit_id)
    if unit is None or unit.position != from_hex:
        await host._send_error(player_id, "Unit position does not match move")
        return True

    budget_rem = float(flow.get("budget_remaining", 0.0))
    max_stack = host._max_active_units_per_hex(current_state, unit_id)
    zoc = host._zoc_hexes_for_unit(current_state, unit_id)
    step_fn = host._movement_step_cost_fn(unit_id)
    if not is_valid_move(
        current_state,
        unit_id,
        to_hex,
        budget_rem,
        zoc_hexes=zoc,
        blocked_hexes=None,
        max_active_units_per_hex=max_stack,
        step_cost=step_fn,
    ):
        await host._send_error(player_id, "Illegal continuation move")
        return True

    step_cost = host._movement_step_total_cost(current_state, unit_id, from_hex, to_hex)
    new_budget = budget_rem - step_cost
    if new_budget < -1e-9:
        await host._send_error(player_id, "Movement budget exhausted")
        return True

    if await drive_movement_arc_event(
        host, player_id, player, "MoveUnit", dict(request.params)
    ):
        flow_after = read_movement_arc(host.action_manager.current_state)
        if flow_after is None:
            if flow.get("retreat_fulfillment"):
                fin = flow.get("finalize_request")
                if isinstance(fin, dict):
                    fin_params = dict(fin)
                    await _complete_retreat_fulfillment_step(
                        host,
                        player_id,
                        player,
                        fin_params=fin_params,
                    )
                    return True
            elif not flow.get("retreat_fulfillment"):
                try:
                    host._spend_action_after_normal_move_unit()
                except Exception as e:
                    host.logger.error(f"Error in turn advancement: {e}", exc_info=True)
        return True

    if flow.get("retreat_fulfillment"):
        ctx = ArcContext(
            state=host.action_manager.current_state,
            session_state_key=host.action_manager.current_state.session_state_key,
            owner_faction=str(player.faction),
            params=dict(request.params),
        )
        if path_complete(ctx):
            fin = flow.get("finalize_request")
            if isinstance(fin, dict):
                host.action_manager.execute(WriteHexengineMovementArc(None))
                return await _complete_retreat_fulfillment_step(
                    host,
                    player_id,
                    player,
                    fin_params=dict(fin),
                )
        cur = read_arc_cursor(host.action_manager.current_state)
        if cur is None or cur.arc_id != MOVEMENT_ARC_ID:
            host.action_manager.execute(WriteHexengineMovementArc(None))
            return True

    await host._send_error(player_id, "Movement arc rejected continuation move")
    return True


async def handle_authority_move_unit_normal(
    host: AuthorityMovementHost,
    player_id: str,
    player: PlayerInfo,
    request: ActionRequest,
    current_state: GameState,
) -> bool:
    """Authority path for non-retreat `MoveUnit`. True if this method fully handled it."""

    flow = read_movement_arc(current_state)
    if flow:
        gate = str(flow.get("gate", ""))
        if gate == MOVEMENT_ARC_GATE_AWAITING_INTERRUPT:
            await host._send_error(
                player_id,
                "Movement is paused for interrupts; use PassMovementInterrupt",
            )
            return True
        if gate == MOVEMENT_ARC_GATE_AWAITING_CONTINUE:
            return await continue_stepwise_move_unit(
                host, player_id, player, request, current_state, flow
            )

    try:
        host._validate_move_unit_request(
            current_state,
            request.params,
            player,
            is_retreat_fulfillment=False,
        )
    except ValueError as e:
        await host._send_error(player_id, str(e))
        return True

    unit_id = str(request.params.get("unit_id", ""))
    fh = request.params.get("from_hex")
    th = request.params.get("to_hex")
    if not isinstance(fh, dict) or not isinstance(th, dict):
        await host._send_error(player_id, "Invalid hex payload")
        return True
    from_hex = Hex(**fh)
    to_hex = Hex(**th)
    ctx = MoveContext(
        state=current_state,
        unit_id=unit_id,
        from_hex=from_hex,
        to_hex=to_hex,
        player_faction=str(player.faction),
        is_retreat_fulfillment=False,
    )
    stepwise_raw = host.hooks.modification.stepwise_enabled(ctx)
    if stepwise_raw is ENGINE_DEFAULT or not bool(stepwise_raw):
        return False

    budget = float(host._movement_budget_for_unit(current_state, unit_id))
    zoc = host._zoc_hexes_for_unit(current_state, unit_id)
    max_stack = host._max_active_units_per_hex(current_state, unit_id)
    step_fn = host._movement_step_cost_fn(unit_id)
    path = shortest_move_path(
        current_state,
        unit_id,
        to_hex,
        budget,
        zoc_hexes=zoc,
        blocked_hexes=None,
        max_active_units_per_hex=max_stack,
        step_cost=step_fn,
    )
    if path is None or len(path) < 2:
        await host._send_error(player_id, "Could not resolve stepwise move path")
        return True
    if len(path) <= 2:
        return False

    step_cost = host._movement_step_total_cost(current_state, unit_id, path[0], path[1])
    if step_cost == float("inf"):
        await host._send_error(player_id, "Illegal stepwise move")
        return True
    budget_rem = budget - step_cost
    first_from, first_to = path[0], path[1]
    try:
        host.action_manager.execute(MoveUnit(unit_id, first_from, first_to))
    except Exception as e:
        await host._send_error(player_id, f"Action failed: {e}")
        return True

    st1 = host.action_manager.current_state
    step_ctx = MovementStepContext(
        state=st1,
        unit_id=unit_id,
        path=path,
        arrived_at_index=1,
        player_faction=str(player.faction),
    )
    iq_raw = host.hooks.modification.interrupt_factions_after_step(step_ctx)
    if iq_raw is ENGINE_DEFAULT:
        interrupts = ()
    else:
        interrupts = dedupe_faction_ids(tuple(str(x) for x in iq_raw if str(x).strip()))

    wire_path = [{"i": int(h.i), "j": int(h.j), "k": int(h.k)} for h in path]
    base_flow: dict[str, Any] = {
        "schema": MOVEMENT_ARC_SCHEMA,
        "unit_id": unit_id,
        "path": wire_path,
        "step_index": 1,
        "moving_faction": str(player.faction),
        "budget_remaining": float(budget_rem),
    }
    if interrupts:
        base_flow["saved_turn"] = turn_state_to_movement_arc_snapshot(st1.turn)
        base_flow["interrupt_queue"] = list(interrupts)
        base_flow["gate"] = MOVEMENT_ARC_GATE_AWAITING_INTERRUPT
        host.action_manager.execute(WriteHexengineMovementArc(base_flow))
        nt = replace(
            host.action_manager.current_state.turn,
            current_faction=interrupts[0],
            current_phase=MOVEMENT_INTERRUPT_PHASE,
            phase_actions_remaining=1,
        )
        host.action_manager.execute(SetTurnState(nt))
    else:
        base_flow["gate"] = MOVEMENT_ARC_GATE_AWAITING_CONTINUE
        base_flow["interrupt_queue"] = []
        base_flow["saved_turn"] = None
        host.action_manager.execute(WriteHexengineMovementArc(base_flow))

    sync_movement_cursor_from_payload(host)
    await host._send_move_unit_success_and_broadcast(player_id)
    return True


async def handle_authority_retreat_path_move_unit(
    host: AuthorityMovementHost,
    player_id: str,
    player: PlayerInfo,
    request: ActionRequest,
    current_state: GameState,
    *,
    retreat_remaining: int,
    uid_for_move: str,
) -> bool:
    """
    Start or continue a stepwise retreat along a client-built ``path`` wire list.

    Returns True when this handler fully processed the request.
    """
    flow = read_movement_arc(current_state)
    if flow and flow.get("retreat_fulfillment"):
        gate = str(flow.get("gate", ""))
        if gate == MOVEMENT_ARC_GATE_AWAITING_CONTINUE:
            return await continue_stepwise_move_unit(
                host, player_id, player, request, current_state, flow
            )
        await host._send_error(
            player_id, "Retreat path move is not awaiting continuation"
        )
        return True

    wire_path = request.params.get("path")
    path = parse_wire_path(wire_path)
    if len(path) < 2:
        return False

    rem = int(retreat_remaining)
    blocked_raw = host.hooks.modification.retreat_blocked(current_state, uid_for_move)
    if blocked_raw is ENGINE_DEFAULT or blocked_raw is None:
        blocked_hexes = None
    else:
        blocked_hexes = (
            blocked_raw
            if isinstance(blocked_raw, frozenset)
            else frozenset(blocked_raw)
        )
    max_stack = host._max_active_units_per_hex(current_state, uid_for_move)
    step_fn = host._movement_step_cost_fn(uid_for_move)

    def _validate_endpoint(
        state: GameState,
        unit_id: str,
        from_hex: Hex,
        to_hex: Hex,
        hexes_remaining: int,
    ) -> None:
        host._validate_move_unit_request(
            state,
            {
                "unit_id": unit_id,
                "from_hex": {"i": from_hex.i, "j": from_hex.j, "k": from_hex.k},
                "to_hex": {"i": to_hex.i, "j": to_hex.j, "k": to_hex.k},
            },
            player,
            is_retreat_fulfillment=True,
        )

    try:
        validate_retreat_path(
            state=current_state,
            unit_id=uid_for_move,
            path=path,
            obligation=rem,
            blocked_hexes=blocked_hexes,
            max_active_units_per_hex=max_stack,
            step_cost=step_fn,
            validate_endpoint=_validate_endpoint,
        )
        validate_retreat_fulfillment_stack(
            host,
            st_before=current_state,
            uid_for_move=uid_for_move,
            player=player,
            request=request,
        )
    except ValueError as e:
        await host._send_error(player_id, str(e))
        return True

    if await drive_movement_arc_retreat_open(
        host, player_id, player, dict(request.params)
    ):
        if read_movement_arc(host.action_manager.current_state) is None:
            fin = retreat_finalize_request_from_params(
                dict(request.params), uid_for_move
            )
            if fin is not None:
                return await _complete_retreat_fulfillment_step(
                    host,
                    player_id,
                    player,
                    fin_params=fin,
                )
        return True

    await host._send_error(
        player_id,
        "Retreat path continuation requires a declared movement arc "
        "(bind ArcHook.MOVEMENT_ARC to ENGINE_MOVEMENT_ARC_PRESET or a custom ArcSpec)",
    )
    return True


__all__ = [
    "AuthorityMovementHost",
    "continue_stepwise_move_unit",
    "dedupe_faction_ids",
    "handle_authority_move_unit_normal",
    "handle_authority_retreat_path_move_unit",
    "path_tuple_from_movement_arc",
    "read_movement_arc",
    "retreat_finalize_request_from_params",
    "retreat_path_wire_deferred_to_movement_arc",
]
