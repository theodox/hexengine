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
    """Context passed to title combat hooks for a single requested attack.

    ``attacker_ids`` and ``defender_ids`` are the full participating parties (often
    length 1). Wire requests still send ``attacker_id`` / ``defender_id`` as anchors;
    the server normalizes optional ``attacker_ids`` / ``defender_ids`` lists in
    ``params`` into these tuples.

    ``attacker_hexes`` / ``defender_hexes`` are the **distinct map hexes** occupied by
    those parties (sorted ``(i, j, k)``), so titles can reason about multi-hex attacks
    without re-walking ``state.board``.

    ``attacker_hex`` / ``defender_hex`` are read-only views of the **anchor** (wire
    primary) units' positions: ``state.board.units[attacker_ids[0]].position`` and the
    same for defenders. If that unit is missing, the first entry of the corresponding
    ``*_hexes`` tuple is used.
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
        """Primary attacker (wire ``attacker_id``); same as ``attacker_ids[0]``."""
        return self.attacker_ids[0]

    @property
    def defender_unit_id(self) -> str:
        """Primary defender (wire ``defender_id``); same as ``defender_ids[0]``."""
        return self.defender_ids[0]

    @property
    def attacker_hex(self) -> Hex:
        """Anchor attacker hex (wire ``attacker_id`` unit)."""
        u = self.state.board.units.get(self.attacker_ids[0])
        if u is not None and u.active:
            return u.position
        if self.attacker_hexes:
            return self.attacker_hexes[0]
        raise ValueError("AttackContext has no attacker hex")

    @property
    def defender_hex(self) -> Hex:
        """Anchor defender hex (wire ``defender_id`` unit)."""
        u = self.state.board.units.get(self.defender_ids[0])
        if u is not None and u.active:
            return u.position
        if self.defender_hexes:
            return self.defender_hexes[0]
        raise ValueError("AttackContext has no defender hex")


@dataclass(frozen=True, slots=True)
class AttackResolution:
    """
    Deterministic resolution returned by a title for a single attack.

    The server uses this to build an engine `Attack` state action. The engine is responsible
    for applying the resolution to `GameState` (extension updates, retreat obligations,
    unit deletion, rng log entry) and broadcasting the resulting wire events.
    """

    outcome: str
    #: When set, overrides ``AttackContext.attacker_ids`` for the engine ``Attack`` action.
    #: When omitted, the server uses ``AttackContext.attacker_ids``.
    attacker_ids: tuple[str, ...] | None = None
    #: When set, overrides ``AttackContext.defender_ids`` for the engine ``Attack`` action.
    #: When omitted, the server uses ``AttackContext.defender_ids``.
    defender_ids: tuple[str, ...] | None = None
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
