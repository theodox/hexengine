"""
Attack/combat-related hooks.

Role in turn resolution:

- The authoritative server receives an `Attack` request from a client.
- It builds an `AttackContext` from the current authoritative `GameState`.
- The title's `AttackHooks` decides:
  - whether the attack is legal (`validate_attack`)
  - what the outcome is (`resolve_attack`)
  - whether the phase should auto-advance after applying it (`auto_advance_phase_after_attack`)
  - whether to open the post-retreat advance gate (`maybe_open_combat_advance_after_retreat`; engine default in `hooks.internal.advance`)
- The engine then applies the outcome as a deterministic state action and broadcasts:
  - per-recipient combat/retreat instructions
  - updated `StateUpdate` snapshots

Returning `ENGINE_DEFAULT` means "use the engine default for this hook point". For attacks, the
engine treats `ENGINE_DEFAULT` from `validate_attack`/`resolve_attack` as "this title does not
support resolving attacks".

**Title wiring:** use `AttackHook` members with `hexengine.hooks.wiring.bind_title_hook`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..hexes.types import Hex
from ..state import GameState, UnitState
from ..state.actions import OpenCombatAdvance
from .core import ENGINE_DEFAULT, RuleViolation


@dataclass(frozen=True, slots=True)
class AttackContext:
    """Context passed to title combat hooks for a single requested attack.

    `attacker_ids` and `defender_ids` are the full participating parties (often
    length 1). Wire requests still send `attacker_id` / `defender_id` as anchors;
    the server normalizes optional `attacker_ids` / `defender_ids` lists in
    `params` into these tuples.

    `attacker_hexes` / `defender_hexes` are the **distinct map hexes** occupied by
    those parties (sorted `(i, j, k)`), so titles can reason about multi-hex attacks
    without re-walking `state.board`.

    `attacker_hex` / `defender_hex` are read-only views of the **anchor** (wire
    primary) units' positions: `state.board.units[attacker_ids[0]].position` and the
    same for defenders. If that unit is missing, the first entry of the corresponding
    `*_hexes` tuple is used.
    """

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
        """Primary attacker (wire `attacker_id`); same as `attacker_ids[0]`."""
        return self.attacker_ids[0]

    @property
    def defender_unit_id(self) -> str:
        """Primary defender (wire `defender_id`); same as `defender_ids[0]`."""
        return self.defender_ids[0]

    @property
    def attacker_hex(self) -> Hex:
        """Anchor attacker hex (wire `attacker_id` unit)."""
        u = self.state.board.units.get(self.attacker_ids[0])
        if u is not None and u.active:
            return u.position
        if self.attacker_hexes:
            return self.attacker_hexes[0]
        raise ValueError("AttackContext has no attacker hex")

    @property
    def defender_hex(self) -> Hex:
        """Anchor defender hex (wire `defender_id` unit)."""
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
    """Inputs for server map-selection preview while drafting an attack plan."""

    state: GameState
    player_faction: str
    draft: dict[str, Any]
    shell_ui: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AttackResolution:
    """
    Deterministic resolution returned by a title for a single attack.

    Snapshot-shaped payloads live on `rng_entry` and `effects`; the server
    normalizes them together via `hexengine.snapshot.attack_resolution_snapshot_fields`
    before building `Attack` and `ApplyCombatEffects`.

    The server uses this to build an engine `Attack` state action. The engine is responsible
    for applying the resolution to `GameState` (extension updates, retreat obligations,
    unit deletion, rng log entry) and broadcasting the resulting state snapshots.
    """

    outcome: str
    #: When set, overrides `AttackContext.attacker_ids` for the engine `Attack` action.
    #: When omitted, the server uses `AttackContext.attacker_ids`.
    attacker_ids: tuple[str, ...] | None = None
    #: When set, overrides `AttackContext.defender_ids` for the engine `Attack` action.
    #: When omitted, the server uses `AttackContext.defender_ids`.
    defender_ids: tuple[str, ...] | None = None
    retreat_distance: int | None = None
    retreat_unit_id: str | None = None
    #: One `rng_log` row (mapping or dataclass normalizing to a dict). The engine
    #: enforces JSON-safe snapshot shape; titles do not call snapshot helpers themselves.
    rng_entry: dict[str, Any] | None = None
    #: Snapshot-shaped follow-up effects applied by the server after `Attack` (step
    #: loss, disruption, optional-retreat gate tweaks, etc.). Schema is title-defined;
    #: see `ApplyCombatEffects` in `hexengine.state.actions`. Nested
    #: `@dataclass` values are normalized by the engine; titles do not call snapshot
    #: helpers themselves.
    effects: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AttackHooks:
    """Combat policy surface consulted by the authoritative server during turn resolution."""

    validate_attack: Callable[[AttackContext], None | object] | None = None
    resolve_attack: Callable[[AttackContext], AttackResolution | object] | None = None
    auto_advance_phase_after_attack: Callable[[GameState], bool | object] | None = None
    maybe_open_combat_advance_after_retreat: (
        Callable[[GameState, str], OpenCombatAdvance | None | object] | None
    ) = None
    attack_plan_preview: (
        Callable[[AttackPlanPreviewContext], dict[str, Any] | object] | None
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

    def advance_after_retreat(
        self, state: GameState, extension_key: str
    ) -> OpenCombatAdvance | None | object:
        """Policy for opening the advance gate after retreat; see `hooks.internal.advance`."""

        if self.maybe_open_combat_advance_after_retreat is None:
            return ENGINE_DEFAULT
        return self.maybe_open_combat_advance_after_retreat(state, extension_key)


class AttackHook(StrEnum):
    """Stable slot ids for `bind_title_hook` (values match `AttackHooks` field names)."""

    VALIDATE_ATTACK = "validate_attack"
    RESOLVE_ATTACK = "resolve_attack"
    AUTO_ADVANCE_PHASE_AFTER_ATTACK = "auto_advance_phase_after_attack"
    MAYBE_OPEN_COMBAT_ADVANCE_AFTER_RETREAT = "maybe_open_combat_advance_after_retreat"
    ATTACK_PLAN_PREVIEW = "attack_plan_preview"


AttackHook._hexengine_hook_bundle = "attack"


def attack_hooks_unsupported() -> AttackHooks:
    """Attack hooks that always return `ENGINE_DEFAULT` at action time.

    Satisfies `validate_title_contract` when the turn schedule includes combat
    phases but a title overrides `TitleHooks` for other areas only. The server still
    rejects `Attack` with the usual unsupported message if players send combat actions.
    """

    def _validate(_ctx: AttackContext) -> object:
        return ENGINE_DEFAULT

    def _resolve(_ctx: AttackContext) -> object:
        return ENGINE_DEFAULT

    return AttackHooks(validate_attack=_validate, resolve_attack=_resolve)


__all__ = [
    "AttackContext",
    "AttackHook",
    "AttackHooks",
    "AttackPlanPreviewContext",
    "AttackResolution",
    "ENGINE_DEFAULT",
    "RuleViolation",
    "attack_hooks_unsupported",
]
