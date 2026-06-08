"""
Runtime guards and effects for the declared stepwise movement arc.

These close over the authoritative server host so step cost, ZOC, and interrupt hooks
stay title-driven while the generic runner owns segment legality and cursor motion.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ...arcs import ArcContext
from ...arcs.movement_arc_decl import path_tuple_from_payload, read_movement_payload
from ...hexes.types import Hex
from ...hooks.core import ENGINE_DEFAULT
from ...hooks.movement import MovementStepContext
from ...state.action_manager import StateAction
from ...state.actions import (
    MoveUnit,
    ResolvePassMovementInterrupt,
    WriteHexengineMovementArc,
)
from ...state.game_state import GameState
from ...state.logic import is_valid_move
from ...state.movement_arc import (
    MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
    MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
    MOVEMENT_INTERRUPT_PHASE,
    turn_state_to_movement_arc_snapshot,
)
from .authority_movement import AuthorityMovementHost, dedupe_faction_ids


class _AdvanceMovementArcAfterStep(StateAction):
    """After one hex step, update the movement arc payload and maybe open interrupts."""

    def __init__(self, host: AuthorityMovementHost, prior_flow: dict[str, Any]) -> None:
        self._host = host
        self._prior_flow = dict(prior_flow)
        self._prev_ext: dict[str, Any] | None = None
        self._prev_turn = None

    def apply(self, state: GameState) -> GameState:
        from ...state.movement_arc import HEXENGINE_MOVEMENT_ARC_KEY
        from ...state.engine_session_state import with_engine_bucket

        self._prev_ext = dict(state.engine_state)
        self._prev_turn = state.turn

        flow = dict(self._prior_flow)
        unit_id = str(flow.get("unit_id", "")).strip()
        path = path_tuple_from_payload(flow)
        idx = int(flow.get("step_index", -1))
        new_idx = idx + 1
        new_flow = dict(flow)
        new_flow["step_index"] = new_idx

        if new_idx >= len(path) - 1:
            new_flow["gate"] = MOVEMENT_ARC_GATE_AWAITING_CONTINUE
            return with_engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY, new_flow)

        step_ctx = MovementStepContext(
            state=state,
            unit_id=unit_id,
            path=path,
            arrived_at_index=new_idx,
            player_faction=str(flow.get("moving_faction", "")),
        )
        iq_raw = self._host.hooks.movement.interrupt_factions_after_step(step_ctx)
        if iq_raw is ENGINE_DEFAULT:
            interrupts: tuple[str, ...] = ()
        else:
            interrupts = dedupe_faction_ids(
                tuple(str(x) for x in iq_raw if str(x).strip())
            )

        if interrupts:
            new_flow["saved_turn"] = turn_state_to_movement_arc_snapshot(state.turn)
            new_flow["interrupt_queue"] = list(interrupts)
            new_flow["gate"] = MOVEMENT_ARC_GATE_AWAITING_INTERRUPT
            st = with_engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY, new_flow)
            nt = replace(
                st.turn,
                current_faction=interrupts[0],
                current_phase=MOVEMENT_INTERRUPT_PHASE,
                phase_actions_remaining=1,
            )
            return st.with_turn(nt)

        new_flow["gate"] = MOVEMENT_ARC_GATE_AWAITING_CONTINUE
        new_flow["interrupt_queue"] = []
        new_flow["saved_turn"] = None
        return with_engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY, new_flow)

    def revert(self, state: GameState) -> GameState:
        if self._prev_ext is None or self._prev_turn is None:
            return state
        return state.with_engine_state(self._prev_ext).with_turn(self._prev_turn)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "<AdvanceMovementArcAfterStep>"


class MovementArcEffects:
    """Host-bound movement arc guards/effects wired into build_movement_arc()."""

    def __init__(self, host: AuthorityMovementHost) -> None:
        self._host = host

    def matches_stepwise_step(self, ctx: ArcContext) -> bool:
        flow = read_movement_payload(ctx.state)
        if not flow:
            return False
        if str(flow.get("gate", "")) != MOVEMENT_ARC_GATE_AWAITING_CONTINUE:
            return False
        if ctx.owner_faction != str(flow.get("moving_faction", "")):
            return False

        unit_id = str(flow.get("unit_id", "")).strip()
        path = path_tuple_from_payload(flow)
        if not unit_id or len(path) < 2:
            return False

        idx = int(flow.get("step_index", -1))
        if idx < 0 or idx >= len(path) - 1:
            return False

        fh, th = ctx.params.get("from_hex"), ctx.params.get("to_hex")
        if not isinstance(fh, dict) or not isinstance(th, dict):
            return False
        from_hex = Hex(**fh)
        to_hex = Hex(**th)
        if from_hex != path[idx] or to_hex != path[idx + 1]:
            return False

        unit = ctx.state.board.units.get(unit_id)
        if unit is None or unit.position != from_hex:
            return False

        budget_rem = float(flow.get("budget_remaining", 0.0))
        max_stack = self._host._max_active_units_per_hex(ctx.state, unit_id)
        zoc = self._host._zoc_hexes_for_unit(ctx.state, unit_id)
        step_fn = self._host._movement_step_cost_fn(unit_id)
        return is_valid_move(
            ctx.state,
            unit_id,
            to_hex,
            budget_rem,
            zoc_hexes=zoc,
            blocked_hexes=None,
            max_active_units_per_hex=max_stack,
            step_cost=step_fn,
        )

    def apply_step(self, ctx: ArcContext) -> list[StateAction]:
        flow = read_movement_payload(ctx.state)
        if not flow:
            return []

        unit_id = str(flow.get("unit_id", "")).strip()
        path_tuple_from_payload(flow)
        int(flow.get("step_index", -1))
        fh, th = ctx.params.get("from_hex"), ctx.params.get("to_hex")
        if not isinstance(fh, dict) or not isinstance(th, dict):
            return []
        from_hex = Hex(**fh)
        to_hex = Hex(**th)

        budget_rem = float(flow.get("budget_remaining", 0.0))
        step_cost = self._host._movement_step_total_cost(
            ctx.state, unit_id, from_hex, to_hex
        )
        new_budget = budget_rem - step_cost
        if new_budget < -1e-9:
            return []

        new_flow = dict(flow)
        new_flow["budget_remaining"] = float(new_budget)
        return [
            MoveUnit(unit_id, from_hex, to_hex),
            _AdvanceMovementArcAfterStep(self._host, new_flow),
        ]

    def finish_path(self, ctx: ArcContext) -> list[StateAction]:
        return [WriteHexengineMovementArc(None)]

    def is_interrupt_responder(self, ctx: ArcContext) -> bool:
        flow = read_movement_payload(ctx.state)
        if not flow:
            return False
        if str(flow.get("gate", "")) != MOVEMENT_ARC_GATE_AWAITING_INTERRUPT:
            return False
        queue = flow.get("interrupt_queue")
        if not isinstance(queue, list) or not queue:
            return False
        head = str(queue[0]).strip()
        return bool(ctx.owner_faction and str(ctx.owner_faction).strip() == head)

    def pass_interrupt(self, ctx: ArcContext) -> list[StateAction]:
        if not ctx.owner_faction:
            return []
        return [ResolvePassMovementInterrupt(str(ctx.owner_faction))]


__all__ = ["MovementArcEffects"]
