"""
Movement-related hooks (movement budget, ZOC, retreat policy).

Role in turn resolution:

- The authoritative server validates `MoveUnit` requests during a player's turn.
- Movement hooks supply title policy for:
  - movement budget, ZOC
  - retreat obligations and retreat routing constraints
  - retreat legality checks (e.g. distance rule)
- whether to auto-advance the turn schedule after a normal move spends an action
  (`auto_advance_phase_after_move_spend`; engine catalog default when the pool is empty)
- The engine then applies the resulting move as a pure state action.
- Optional **stepwise** moves implement a **movement arc** (see **Arc** / **Segment** in
  `hexengine.state.movement_arc`): each hex step is a segment; titles may insert
  interrupt segments via `MovementInterrupt` and `PassMovementInterrupt`. Stepwise
  behavior is off unless a title implements the matching hooks below.

Thin clients do not execute these hooks. Drag previews use `unit_preview_request` /
`marker_preview_request` RPCs; the server runs these hooks when building legal hex sets
(see `hexengine.server.preview`). Clients read `turn_rules.movement_budget` only to rebuild
a thin `GameDefinition` for advance-turn UI, not to compute move highlights locally.

**Author layout:** implement policy in pack-root ``movement_rules.py`` (see
``MovementRulesBinding`` in `hexengine.hooks.movement_rules`). Keep ``hooks/movement.py``
as thin ``bind_title_hook`` adapters; preview hooks may stay in hooks. Stepwise payload
and movement arc cursor sync are engine-owned (``authority_movement``, movement arc
runner).

**Title wiring:** import `MovementHook` and `hexengine.hooks.wiring.bind_title_hook`.
Use `@bind_title_hook(MovementHook.MOVEMENT_BUDGET_FOR_UNIT)` (and siblings) so hook
slots are not stringly-typed at call sites. Legacy `\"movement.field\"` paths still work.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..hexes.types import Hex
from ..state import GameState
from .core import ENGINE_DEFAULT, RuleViolation


@dataclass(frozen=True, slots=True)
class MoveContext:
    """Context for validating a single move attempt (normal move or retreat fulfillment)."""

    state: GameState
    unit_id: str
    from_hex: Hex
    to_hex: Hex
    player_faction: str
    is_retreat_fulfillment: bool = False


@dataclass(frozen=True, slots=True)
class RetreatPathPreviewContext:
    """Inputs for ``map_selection_preview`` when ``kind`` is ``retreat_path``."""

    state: GameState
    player_faction: str
    draft: dict[str, Any]
    shell_ui: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MovementStepContext:
    """Context after one step of a stepwise move; `arrived_at_index` indexes `path`."""

    state: GameState
    unit_id: str
    path: tuple[Hex, ...]
    arrived_at_index: int
    player_faction: str


@dataclass(frozen=True, slots=True)
class MovementHooks:
    """
    Movement policy surface consulted by the authoritative server during turn resolution.

    Any hook may be omitted. When omitted (or when it returns `ENGINE_DEFAULT`), the engine uses
    its default behavior for that hook point.

    Hooks should not mutate `state`. Return data to guide engine behavior or raise to reject.
    """

    movement_budget_for_unit: Callable[[GameState, str], float | object] | None = None
    zoc_hexes_for_unit: (
        Callable[[GameState, str], frozenset[Hex] | None | object] | None
    ) = None
    retreat_group_unit_ids: (
        Callable[[GameState, str], tuple[str, ...] | object] | None
    ) = None
    retreat_obligation_hexes_remaining: (
        Callable[[GameState, str], int | None | object] | None
    ) = None
    any_retreat_obligation_pending: Callable[[GameState], bool | object] | None = None
    faction_has_pending_retreat_obligation: (
        Callable[[GameState, str], bool | object] | None
    ) = None
    retreat_blocked_hexes: (
        Callable[[GameState, str], frozenset[Hex] | None | object] | None
    ) = None
    validate_retreat_move: Callable[[MoveContext, int], None | object] | None = None
    validate_move: Callable[[MoveContext], None | object] | None = None
    movement_step_cost_for_unit: (
        Callable[[GameState, str, Hex, Hex, float], float | object] | None
    ) = None
    resolve_move_as_steps: Callable[[MoveContext], bool | object] | None = None
    movement_interrupt_factions_after_step: (
        Callable[[MovementStepContext], tuple[str, ...] | object] | None
    ) = None
    retreat_path_preview: (
        Callable[[RetreatPathPreviewContext], dict[str, Any] | object] | None
    ) = None
    auto_advance_phase_after_move_spend: (
        Callable[[GameState], bool | object] | None
    ) = None

    def budget(self, state: GameState, unit_id: str) -> float | object:
        if self.movement_budget_for_unit is None:
            return ENGINE_DEFAULT
        return self.movement_budget_for_unit(state, unit_id)

    def zoc(self, state: GameState, unit_id: str) -> frozenset[Hex] | None | object:
        if self.zoc_hexes_for_unit is None:
            return ENGINE_DEFAULT
        return self.zoc_hexes_for_unit(state, unit_id)

    def retreat_group(self, state: GameState, unit_id: str) -> tuple[str, ...] | object:
        if self.retreat_group_unit_ids is None:
            return ENGINE_DEFAULT
        return self.retreat_group_unit_ids(state, unit_id)

    def retreat_remaining(self, state: GameState, unit_id: str) -> int | None | object:
        if self.retreat_obligation_hexes_remaining is None:
            return ENGINE_DEFAULT
        return self.retreat_obligation_hexes_remaining(state, unit_id)

    def any_retreat_pending(self, state: GameState) -> bool | object:
        if self.any_retreat_obligation_pending is None:
            return ENGINE_DEFAULT
        return self.any_retreat_obligation_pending(state)

    def faction_retreat_pending(self, state: GameState, faction: str) -> bool | object:
        if self.faction_has_pending_retreat_obligation is None:
            return ENGINE_DEFAULT
        return self.faction_has_pending_retreat_obligation(state, faction)

    def retreat_blocked(
        self, state: GameState, unit_id: str
    ) -> frozenset[Hex] | None | object:
        if self.retreat_blocked_hexes is None:
            return ENGINE_DEFAULT
        return self.retreat_blocked_hexes(state, unit_id)

    def validate_retreat(self, ctx: MoveContext, hexes_remaining: int) -> None | object:
        if self.validate_retreat_move is None:
            return ENGINE_DEFAULT
        return self.validate_retreat_move(ctx, int(hexes_remaining))

    def validate(self, ctx: MoveContext) -> None | object:
        if self.validate_move is None:
            return ENGINE_DEFAULT
        return self.validate_move(ctx)

    def step_cost_move(
        self, state: GameState, unit_id: str, from_h: Hex, to_h: Hex, base: float
    ) -> float | object:
        if self.movement_step_cost_for_unit is None:
            return ENGINE_DEFAULT
        return self.movement_step_cost_for_unit(state, unit_id, from_h, to_h, base)

    def stepwise_enabled(self, ctx: MoveContext) -> bool | object:
        if self.resolve_move_as_steps is None:
            return ENGINE_DEFAULT
        return self.resolve_move_as_steps(ctx)

    def interrupt_factions_after_step(
        self, ctx: MovementStepContext
    ) -> tuple[str, ...] | object:
        if self.movement_interrupt_factions_after_step is None:
            return ENGINE_DEFAULT
        return self.movement_interrupt_factions_after_step(ctx)

    def retreat_path_preview_for(
        self, ctx: RetreatPathPreviewContext
    ) -> dict[str, Any] | object:
        if self.retreat_path_preview is None:
            return ENGINE_DEFAULT
        return self.retreat_path_preview(ctx)

    def auto_advance_after_move_spend(self, state: GameState) -> bool | object:
        if self.auto_advance_phase_after_move_spend is None:
            return ENGINE_DEFAULT
        return self.auto_advance_phase_after_move_spend(state)


class MovementHook(StrEnum):
    """Stable slot ids for `bind_title_hook` (values match `MovementHooks` field names)."""

    MOVEMENT_BUDGET_FOR_UNIT = "movement_budget_for_unit"
    ZOC_HEXES_FOR_UNIT = "zoc_hexes_for_unit"
    RETREAT_GROUP_UNIT_IDS = "retreat_group_unit_ids"
    RETREAT_OBLIGATION_HEXES_REMAINING = "retreat_obligation_hexes_remaining"
    ANY_RETREAT_OBLIGATION_PENDING = "any_retreat_obligation_pending"
    FACTION_HAS_PENDING_RETREAT_OBLIGATION = "faction_has_pending_retreat_obligation"
    RETREAT_BLOCKED_HEXES = "retreat_blocked_hexes"
    VALIDATE_RETREAT_MOVE = "validate_retreat_move"
    VALIDATE_MOVE = "validate_move"
    MOVEMENT_STEP_COST_FOR_UNIT = "movement_step_cost_for_unit"
    RESOLVE_MOVE_AS_STEPS = "resolve_move_as_steps"
    MOVEMENT_INTERRUPT_FACTIONS_AFTER_STEP = "movement_interrupt_factions_after_step"
    RETREAT_PATH_PREVIEW = "retreat_path_preview"
    AUTO_ADVANCE_PHASE_AFTER_MOVE_SPEND = "auto_advance_phase_after_move_spend"


MovementHook._hexengine_hook_bundle = "movement"


__all__ = [
    "ENGINE_DEFAULT",
    "MoveContext",
    "MovementHook",
    "MovementHooks",
    "MovementStepContext",
    "RetreatPathPreviewContext",
    "RuleViolation",
]
