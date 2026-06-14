"""
Interaction hooks (``Attack`` policy and related preview/outcome hooks).

Role in turn resolution:

- The authoritative server receives an `Attack` request from a client.
- It builds an `AttackContext` from the current authoritative `GameState`.
- The title's `InteractionHooks` decides legality, resolution, auto-advance, and optional
  post-attack bucket outcome.
- The engine applies outcomes as deterministic state actions and broadcasts updates.

**Title wiring:** `InteractionHook` + `hexengine.hooks.wiring.bind_title_hook`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..hexes.types import Hex
from ..state import GameState, UnitState
from .core import ENGINE_DEFAULT, RuleViolation


@dataclass(frozen=True, slots=True)
class AttackContext:
    """Context passed to title interaction hooks for a single requested attack."""

    state: GameState
    attacker_ids: tuple[str, ...]
    defender_ids: tuple[str, ...]
    attacker_hexes: tuple[Hex, ...]
    defender_hexes: tuple[Hex, ...]
    player_faction: str
    attack_kind: str
    params: dict[str, Any]

    @property
    def attacker_unit_id(self) -> str:
        return self.attacker_ids[0]

    @property
    def defender_unit_id(self) -> str:
        return self.defender_ids[0]

    @property
    def attacker_hex(self) -> Hex:
        u = self.state.board.units.get(self.attacker_ids[0])
        if u is not None and u.active:
            return u.position
        if self.attacker_hexes:
            return self.attacker_hexes[0]
        raise ValueError("AttackContext has no attacker hex")

    @property
    def defender_hex(self) -> Hex:
        u = self.state.board.units.get(self.defender_ids[0])
        if u is not None and u.active:
            return u.position
        if self.defender_hexes:
            return self.defender_hexes[0]
        raise ValueError("AttackContext has no defender hex")

    @property
    def attacker_units(self) -> list[UnitState | None]:
        return [self.state.board.units.get(aid) for aid in self.attacker_ids]

    @property
    def defender_units(self) -> list[UnitState | None]:
        return [self.state.board.units.get(did) for did in self.defender_ids]


@dataclass(frozen=True, slots=True)
class AttackPlanPreviewContext:
    """Inputs for ``map_selection_preview`` when ``kind`` is ``attack_plan``."""

    state: GameState
    player_faction: str
    draft: dict[str, Any]
    shell_ui: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AttackResolution:
    """Deterministic resolution returned by a title for a single attack."""

    outcome: str
    attacker_ids: tuple[str, ...] | None = None
    defender_ids: tuple[str, ...] | None = None
    retreat_distance: int | None = None
    retreat_unit_id: str | None = None
    rng_entry: dict[str, Any] | None = None
    effects: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AfterAttackAppliedContext:
    """State after ``Attack`` and ``ApplyCombatEffects``; title follow-up actions."""

    state: GameState
    attack_context: AttackContext
    resolution: AttackResolution
    session_state_key: str
    player_faction: str


@dataclass(frozen=True, slots=True)
class CombatAdvanceMoveContext:
    """Inputs for detecting whether a `MoveUnit` wire fulfills a combat advance."""

    state: GameState
    params: dict[str, Any]
    session_state_key: str
    player_faction: str


@dataclass(frozen=True, slots=True)
class InteractionHooks:
    """Interaction policy consulted by the authoritative server during turn resolution."""

    validate_attack: Callable[[AttackContext], None | object] | None = None
    resolve_attack: Callable[[AttackContext], AttackResolution | object] | None = None
    auto_advance_phase_after_attack: Callable[[GameState], bool | object] | None = None
    attack_plan_preview: (
        Callable[[AttackPlanPreviewContext], object] | None
    ) = None
    combat_outcome_after_applied: (
        Callable[[AfterAttackAppliedContext], object] | None
    ) = None

    def validate(self, ctx: AttackContext) -> None | object:
        if self.validate_attack is None:
            return ENGINE_DEFAULT
        return self.validate_attack(ctx)

    def resolve(self, ctx: AttackContext) -> AttackResolution | object:
        if self.resolve_attack is None:
            return ENGINE_DEFAULT
        return self.resolve_attack(ctx)

    def auto_advance(self, state: GameState) -> bool | object:
        if self.auto_advance_phase_after_attack is None:
            return ENGINE_DEFAULT
        return self.auto_advance_phase_after_attack(state)

    def build_combat_outcome_after_applied(
        self, ctx: AfterAttackAppliedContext
    ) -> object:
        if self.combat_outcome_after_applied is None:
            return ENGINE_DEFAULT
        return self.combat_outcome_after_applied(ctx)


class InteractionHook(StrEnum):
    """Stable slot ids for `bind_title_hook` (values match `InteractionHooks` fields)."""

    VALIDATE_ATTACK = "validate_attack"
    RESOLVE_ATTACK = "resolve_attack"
    AUTO_ADVANCE_PHASE_AFTER_ATTACK = "auto_advance_phase_after_attack"
    ATTACK_PLAN_PREVIEW = "attack_plan_preview"
    COMBAT_OUTCOME_AFTER_APPLIED = "combat_outcome_after_applied"


InteractionHook._hexengine_hook_bundle = "interaction"


def interaction_hooks_unsupported() -> InteractionHooks:
    """Interaction hooks that always return `ENGINE_DEFAULT` at action time."""

    def _validate(_ctx: AttackContext) -> object:
        return ENGINE_DEFAULT

    def _resolve(_ctx: AttackContext) -> object:
        return ENGINE_DEFAULT

    return InteractionHooks(validate_attack=_validate, resolve_attack=_resolve)


__all__ = [
    "AfterAttackAppliedContext",
    "AttackContext",
    "AttackPlanPreviewContext",
    "AttackResolution",
    "CombatAdvanceMoveContext",
    "ENGINE_DEFAULT",
    "InteractionHook",
    "InteractionHooks",
    "RuleViolation",
    "interaction_hooks_unsupported",
]
