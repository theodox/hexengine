"""
Attack/combat-related hooks.

Role in turn resolution:

- The authoritative server receives an `Attack` request from a client.
- It builds an `AttackContext` from the current authoritative `GameState`.
- The title's `AttackHooks` decides:
  - whether the attack is legal (`validate_attack`)
  - what the outcome is (`resolve_attack`)
  - whether the phase should auto-advance after applying it (`auto_advance_phase_after_attack`)
- The engine then applies the outcome as a deterministic state action and broadcasts:
  - per-recipient combat/retreat instructions
  - updated `StateUpdate` snapshots

Returning `DEFAULT` means "use the engine default for this hook point". For attacks, the
engine treats `DEFAULT` from `validate_attack`/`resolve_attack` as "this title does not
support resolving attacks".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..hexes.types import Hex
from ..state import GameState
from .core import DEFAULT


@dataclass(frozen=True, slots=True)
class AttackContext:
    """Context passed to title combat hooks for a single requested attack."""
    state: GameState
    attacker_unit_id: str
    defender_unit_id: str
    attacker_hex: Hex
    defender_hex: Hex
    player_faction: str
    attack_kind: str
    params: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AttackResolution:
    """
    Deterministic resolution returned by a title for a single attack.

    The server uses this to build an engine `Attack` state action. The engine is responsible
    for applying the resolution to `GameState` (extension updates, retreat obligations,
    unit deletion, rng log entry) and broadcasting the resulting wire events.
    """

    outcome: str
    retreat_distance: int | None = None
    retreat_unit_id: str | None = None
    rng_entry: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class AttackHooks:
    """Combat policy surface consulted by the authoritative server during turn resolution."""
    validate_attack: Callable[[AttackContext], None | object] | None = None
    resolve_attack: Callable[[AttackContext], AttackResolution | object] | None = None
    auto_advance_phase_after_attack: Callable[[GameState], bool | object] | None = None

    def validate(self, ctx: AttackContext) -> None | object:
        if self.validate_attack is None:
            return DEFAULT
        return self.validate_attack(ctx)

    def resolve(self, ctx: AttackContext) -> AttackResolution | object:
        if self.resolve_attack is None:
            return DEFAULT
        return self.resolve_attack(ctx)

    def auto_advance(self, state: GameState) -> bool | object:
        if self.auto_advance_phase_after_attack is None:
            return DEFAULT
        return self.auto_advance_phase_after_attack(state)


__all__ = [
    "AttackContext",
    "AttackResolution",
    "AttackHooks",
]

