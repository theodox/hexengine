"""
Hexdemo movement policy (pure rules).

``hooks/movement.py`` wires ``BINDING`` to ``MovementHook`` slots. Preview RPCs stay
in hooks (``retreat_path_preview`` delegates to ``retreat_path_preview.py``).
"""

from __future__ import annotations

from dataclasses import dataclass

from hexengine.hexes.math import distance
from hexengine.hexes.types import Hex
from hexengine.hooks.core import ENGINE_DEFAULT
from hexengine.state import (
    GameState,
    edge_movement_extra_for_neighbor_step,
    linear_features_on_neighbor_step,
    min_linear_movement_cost_for_tags,
)
from hexengine.state.logic import (
    adjacent_enemy_zoc_hexes,
    retreat_impassable_enemy_zoc_hexes,
)

from . import session_state


@dataclass(frozen=True, slots=True)
class HexdemoMovementRules:
    """MovementRulesBinding for hexdemo."""

    def movement_step_cost_for_unit(
        self,
        state: GameState,
        unit_id: str,
        from_hex: Hex,
        to_hex: Hex,
        base_cost: float,
    ) -> float:
        tags_on_step: list[str] = []
        for lf in linear_features_on_neighbor_step(state.board, from_hex, to_hex):
            tags_on_step.extend(lf.tags)
        linear = (
            min_linear_movement_cost_for_tags(state.board, tags_on_step)
            if tags_on_step
            else None
        )
        step_base = float(linear) if linear is not None else base_cost
        return step_base + edge_movement_extra_for_neighbor_step(
            state.board, from_hex, to_hex
        )

    def movement_budget_for_unit(
        self, state: GameState, unit_id: str
    ) -> float | object:
        u = state.board.units.get(unit_id)
        if u is None:
            raise ValueError(f"Unknown unit {unit_id!r}")
        raw = u.attributes.get("movement")
        if raw is not None:
            return float(raw)
        return ENGINE_DEFAULT

    def zoc_hexes_for_unit(self, state: GameState, unit_id: str) -> frozenset[Hex]:
        return adjacent_enemy_zoc_hexes(state, unit_id)

    def retreat_obligation_hexes_remaining(
        self, state: GameState, unit_id: str
    ) -> int | None:
        return session_state.retreat_hexes_remaining(state, unit_id)

    def any_retreat_obligation_pending(self, state: GameState) -> bool:
        return session_state.any_retreat_obligation_pending(state)

    def faction_has_pending_retreat_obligation(
        self, state: GameState, faction: str
    ) -> bool:
        return session_state.faction_has_pending_retreat(state, faction)

    def retreat_blocked_hexes(self, state: GameState, unit_id: str) -> frozenset[Hex]:
        enemy_ring = adjacent_enemy_zoc_hexes(state, unit_id)
        return retreat_impassable_enemy_zoc_hexes(
            state, unit_id, enemy_zoc_ring=enemy_ring
        )

    def validate_retreat_move(self, ctx, hexes_remaining: int) -> None:
        leg = distance(ctx.from_hex, ctx.to_hex)
        if leg != int(hexes_remaining):
            raise ValueError(
                f"Retreat move must cover exactly {int(hexes_remaining)} hexes "
                f"(cube distance); got {leg}"
            )

    def auto_advance_phase_after_move_spend(self, state: GameState) -> bool:
        from .arc_segment import phase_advance_blocked  # breaks cycle: movement_rules → arc_segment → hooks → movement

        if phase_advance_blocked(state):
            return False
        return int(state.turn.phase_actions_remaining) <= 0


BINDING = HexdemoMovementRules()


__all__ = [
    "BINDING",
    "HexdemoMovementRules",
]
