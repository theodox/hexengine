"""
State-based actions for the immutable state system.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from ..hexes.types import Hex
from .action_manager import StateAction

if TYPE_CHECKING:
    from ..state.game_state import GameState

LOGGER = logging.getLogger("actions")


class MoveUnit(StateAction):
    """Action to move a unit from one hex to another.

    This is a pure state transformation - no side effects, no mutations.
    """

    def __init__(self, unit_id: str, from_hex: Hex, to_hex: Hex):
        self.unit_id = unit_id
        self.from_hex = from_hex
        self.to_hex = to_hex
        self.prev_stack_index: int | None = None

    def apply(self, state: GameState) -> GameState:
        """Apply the move, returning a new game state."""
        # Get the unit
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id} not found in state")

        # Verify it's at the expected position
        if unit.position != self.from_hex:
            raise ValueError(
                f"Unit {self.unit_id} is at {unit.position}, not at expected {self.from_hex}"
            )

        self.prev_stack_index = unit.stack_index
        si = state.board.next_stack_index_at_hex(self.to_hex, exclude_unit_id=self.unit_id)
        new_unit = unit.with_position(self.to_hex).with_stack_index(si)

        # Create new board with updated unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)

    def revert(self, state: GameState) -> GameState:
        """Revert the move, returning a new game state."""
        # Get the unit
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id} not found in state")

        psi = (
            self.prev_stack_index
            if self.prev_stack_index is not None
            else unit.stack_index
        )
        new_unit = unit.with_position(self.from_hex).with_stack_index(psi)

        # Create new board with updated unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<MoveUnit '{self.unit_id}', {self.from_hex} -> {self.to_hex}>"


class PatchUnitAttributes(StateAction):
    """Shallow-merge keys into ``UnitState.attributes`` (title-defined JSON-safe data)."""

    def __init__(
        self,
        unit_id: str,
        patch: dict[str, Any],
        *,
        remove_keys: tuple[str, ...] = (),
    ):
        self.unit_id = unit_id
        self.patch = dict(patch)
        self.remove_keys = tuple(remove_keys)
        self._prev_attributes: dict[str, Any] | None = None

    def apply(self, state: GameState) -> GameState:
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id!r} not found")
        self._prev_attributes = dict(unit.attributes)
        new_unit = unit.with_attributes(self.patch, remove_keys=self.remove_keys)
        return state.with_board(state.board.with_unit(new_unit))

    def revert(self, state: GameState) -> GameState:
        unit = state.board.units.get(self.unit_id)
        if unit is None or self._prev_attributes is None:
            return state
        new_unit = replace(unit, attributes=dict(self._prev_attributes))
        return state.with_board(state.board.with_unit(new_unit))

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<PatchUnitAttributes {self.unit_id!r} patch={self.patch!r}>"


class DeleteUnit(StateAction):
    """Action to deactivate a unit (soft delete).

    Sets the unit's active flag to False rather than removing it entirely.
    This allows for undo and preserves the unit's data.
    """

    def __init__(self, unit_id: str):
        self.unit_id = unit_id

    def apply(self, state: GameState) -> GameState:
        """Deactivate the unit, returning a new game state."""
        # Get the unit
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id} not found in state")

        # Create new unit with active=False
        new_unit = unit.with_active(False)

        # Create new board with updated unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)

    def revert(self, state: GameState) -> GameState:
        """Reactivate the unit, returning a new game state."""
        # Get the unit
        unit = state.board.units.get(self.unit_id)
        if unit is None:
            raise ValueError(f"Unit {self.unit_id} not found in state")

        # Create new unit with active=True
        new_unit = unit.with_active(True)

        # Create new board with updated unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<DeleteUnit '{self.unit_id}'>"


class AddUnit(StateAction):
    """Action to add a new unit to the game."""

    def __init__(
        self,
        unit_id: str,
        unit_type: str,
        faction: str,
        position: Hex,
        health: int = 100,
        *,
        stack_index: int | None = None,
        graphics: str | None = None,
        attributes: dict[str, Any] | None = None,
    ):
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.faction = faction
        self.position = position
        self.health = health
        self.stack_index = stack_index
        self.graphics = graphics
        self.attributes = dict(attributes) if attributes else {}

    def apply(self, state: GameState) -> GameState:
        """Add the unit, returning a new game state."""
        from ..state.game_state import UnitState

        # Check if unit already exists
        if self.unit_id in state.board.units:
            raise ValueError(f"Unit {self.unit_id} already exists")

        si = (
            int(self.stack_index)
            if self.stack_index is not None
            else state.board.next_stack_index_at_hex(self.position)
        )

        # Create new unit
        new_unit = UnitState(
            unit_id=self.unit_id,
            unit_type=self.unit_type,
            faction=self.faction,
            position=self.position,
            health=self.health,
            active=True,
            stack_index=si,
            graphics=self.graphics,
            attributes=dict(self.attributes),
        )

        # Create new board with added unit
        new_board = state.board.with_unit(new_unit)

        # Create new game state with updated board
        return state.with_board(new_board)

    def revert(self, state: GameState) -> GameState:
        """Remove the unit, returning a new game state."""
        # Create new board without the unit
        new_board = state.board.without_unit(self.unit_id)

        # Create new game state with updated board
        return state.with_board(new_board)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<AddUnit '{self.unit_id}' ({self.faction} {self.unit_type}) at {self.position}>"


class SpendAction(StateAction):
    """Action to spend action points in the current phase."""

    def __init__(self, amount: int = 1):
        self.amount = amount
        self.previous_remaining = None  # Stored for undo

    def apply(self, state: GameState) -> GameState:
        """Spend actions, returning a new game state."""
        # Store previous value for undo
        self.previous_remaining = state.turn.phase_actions_remaining

        # Create new turn state with actions spent
        new_turn = state.turn.with_actions_spent(self.amount)

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def revert(self, state: GameState) -> GameState:
        """Restore spent actions, returning a new game state."""
        from dataclasses import replace

        current_phase = state.turn.current_phase
        current_faction = state.turn.current_faction

        # Restore previous action count
        new_turn = replace(state.turn, phase_actions_remaining=self.previous_remaining)

        if (
            new_turn.current_phase != current_phase
            or new_turn.current_faction != current_faction
        ):
            LOGGER.warning(
                "Phase or faction changed since SpendAction was applied; cannot revert accurately."
            )
            return state  # No change if phase/faction differ

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def should_revert_prior(self):
        return True

    def __repr__(self) -> str:
        return f"<SpendAction {self.amount}>"


class NextPhase(StateAction):
    """Action to advance to the next phase/turn."""

    def __init__(
        self,
        new_faction: str,
        new_phase: str,
        max_actions: int,
        *,
        new_schedule_index: int,
    ):
        self.new_faction = new_faction
        self.new_phase = new_phase
        self.max_actions = max_actions
        self.new_schedule_index = int(new_schedule_index)
        # Store previous values for undo
        self.prev_faction = None
        self.prev_phase = None
        self.prev_actions = None
        self.prev_schedule_index = None
        self.prev_global_tick: int | None = None

    def apply(self, state: GameState) -> GameState:
        """Advance to next phase, returning a new game state."""
        # Store previous values for undo
        self.prev_faction = state.turn.current_faction
        self.prev_phase = state.turn.current_phase
        self.prev_actions = state.turn.phase_actions_remaining
        self.prev_schedule_index = state.turn.schedule_index
        self.prev_global_tick = state.turn.global_tick

        # Create new turn state for next phase
        new_turn = state.turn.with_next_phase(
            self.new_faction,
            self.new_phase,
            self.max_actions,
            schedule_index=self.new_schedule_index,
            global_tick=int(self.prev_global_tick) + 1,
        )

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def revert(self, state: GameState) -> GameState:
        """Restore previous phase, returning a new game state."""
        # Restore previous phase
        pg = int(self.prev_global_tick) if self.prev_global_tick is not None else 0
        new_turn = state.turn.with_next_phase(
            self.prev_faction,
            self.prev_phase,
            self.prev_actions,
            schedule_index=int(self.prev_schedule_index),
            global_tick=pg,
        )

        # Create new game state with updated turn
        return state.with_turn(new_turn)

    def should_revert_prior(self):
        return False

    def __repr__(self) -> str:
        return (
            f"<NextPhase {self.new_faction}-{self.new_phase}@{self.new_schedule_index}>"
        )


@dataclass(frozen=True)
class MoveMarker:
    """Move a map marker by id (server-side list update; not a `StateAction`)."""

    marker_id: str
    from_hex: Hex
    to_hex: Hex

    def __repr__(self) -> str:
        return f"<MoveMarker {self.marker_id!r} {self.from_hex} -> {self.to_hex}>"


@dataclass(frozen=True)
class AddMarker:
    """Add a marker row (server-side list update; not a `StateAction`)."""

    marker_id: str
    marker_type: str
    position: Hex
    active: bool = True

    def __repr__(self) -> str:
        return (
            f"<AddMarker {self.marker_id!r} type={self.marker_type!r} {self.position}>"
        )


@dataclass(frozen=True)
class RemoveMarker:
    """Remove a marker by id from the server marker list."""

    marker_id: str

    def __repr__(self) -> str:
        return f"<RemoveMarker {self.marker_id!r}>"


_HEXDEMO_COMBAT_KEYS = (
    "attacks_this_phase",
    "retreat_obligations",
    "combat_gate",
    "last_combat",
)


class ClearHexdemoCombatExtension(StateAction):
    """Remove Hexdemo combat prototype keys from ``extension['hexdemo']`` (phase rollover)."""

    def __init__(self) -> None:
        self._saved_hexdemo: dict[str, Any] | None = None

    def apply(self, state: GameState) -> GameState:
        ext = dict(state.extension)
        hx = ext.get("hexdemo")
        if not isinstance(hx, dict):
            self._saved_hexdemo = None
            return state
        self._saved_hexdemo = dict(hx)
        new_hx = {**hx}
        for k in _HEXDEMO_COMBAT_KEYS:
            new_hx.pop(k, None)
        ext["hexdemo"] = new_hx
        return state.with_extension(ext)

    def revert(self, state: GameState) -> GameState:
        if self._saved_hexdemo is None:
            return state
        ext = dict(state.extension)
        ext["hexdemo"] = dict(self._saved_hexdemo)
        return state.with_extension(ext)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "<ClearHexdemoCombatExtension>"


class ClearUnitRetreatObligation(StateAction):
    """Clear one unit's entry from ``hexdemo.retreat_obligations`` after a fulfillment move."""

    def __init__(self, unit_id: str) -> None:
        self.unit_id = unit_id
        self._saved_hexdemo: dict[str, Any] | None = None

    def apply(self, state: GameState) -> GameState:
        ext = dict(state.extension)
        hx = ext.get("hexdemo")
        if not isinstance(hx, dict):
            self._saved_hexdemo = None
            return state
        self._saved_hexdemo = dict(hx)
        new_hx = {**hx}
        ro = dict(new_hx.get("retreat_obligations", {}))
        ro.pop(self.unit_id, None)
        new_hx["retreat_obligations"] = ro
        if not _retreat_obligations_have_pending(ro):
            new_hx.pop("combat_gate", None)
        ext["hexdemo"] = new_hx
        return state.with_extension(ext)

    def revert(self, state: GameState) -> GameState:
        if self._saved_hexdemo is None:
            return state
        ext = dict(state.extension)
        ext["hexdemo"] = dict(self._saved_hexdemo)
        return state.with_extension(ext)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<ClearUnitRetreatObligation {self.unit_id!r}>"


def _retreat_obligations_have_pending(ro: dict[str, Any]) -> bool:
    for v in ro.values():
        try:
            if int(v) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


class Attack(StateAction):
    """Single attack action (``attack_kind`` dispatches); v1 implements ``adjacent`` only."""

    _OUTCOMES = (
        "none",
        "attacker_retreat",
        "defender_retreat",
        "defender_destroyed",
    )

    def __init__(self, attack_kind: str, attacker_id: str, defender_id: str) -> None:
        self.attack_kind = attack_kind
        self.attacker_id = attacker_id
        self.defender_id = defender_id
        self._prev_hexdemo: dict[str, Any] | None = None
        self._prev_rng_log: tuple[dict[str, Any], ...] | None = None
        self._delete_applied = False

    def apply(self, state: GameState) -> GameState:
        if self.attack_kind != "adjacent":
            raise ValueError(f"Unknown attack_kind {self.attack_kind!r}")

        attacker = state.board.units.get(self.attacker_id)
        defender = state.board.units.get(self.defender_id)
        if attacker is None or not attacker.active:
            raise ValueError(f"Attacker {self.attacker_id!r} not found or inactive")
        if defender is None or not defender.active:
            raise ValueError(f"Defender {self.defender_id!r} not found or inactive")
        if attacker.faction == defender.faction:
            raise ValueError("Cannot attack same faction")

        hx0 = state.extension.get("hexdemo")
        self._prev_hexdemo = dict(hx0) if isinstance(hx0, dict) else {}
        self._prev_rng_log = state.rng_log

        outcome = random.choice(self._OUTCOMES)
        retreat_distance: int | None
        if outcome in ("attacker_retreat", "defender_retreat"):
            retreat_distance = random.randint(1, 3)
        else:
            retreat_distance = None

        rng_entry: dict[str, Any] = {
            "op": "adjacent_attack",
            "outcome": outcome,
            "attacker_id": self.attacker_id,
            "defender_id": self.defender_id,
            "retreat_distance": retreat_distance,
        }
        new_rng = state.rng_log + (rng_entry,)

        hx = dict(self._prev_hexdemo)
        prev_attacks = hx.get("attacks_this_phase")
        attacks = list(prev_attacks) if isinstance(prev_attacks, list) else []
        attacks.append(self.attacker_id)
        hx["attacks_this_phase"] = attacks

        prev_ro = hx.get("retreat_obligations")
        retreat_obligations: dict[str, int] = (
            dict(prev_ro) if isinstance(prev_ro, dict) else {}
        )
        retreat_unit_id: str | None = None
        if outcome == "attacker_retreat":
            assert retreat_distance is not None
            retreat_obligations[self.attacker_id] = retreat_distance
            retreat_unit_id = self.attacker_id
            hx["combat_gate"] = "awaiting_retreat"
        elif outcome == "defender_retreat":
            assert retreat_distance is not None
            retreat_obligations[self.defender_id] = retreat_distance
            retreat_unit_id = self.defender_id
            hx["combat_gate"] = "awaiting_retreat"
        else:
            hx.pop("combat_gate", None)

        if outcome == "defender_destroyed":
            retreat_obligations.pop(self.defender_id, None)

        hx["retreat_obligations"] = retreat_obligations
        hx["last_combat"] = {
            "attack_kind": self.attack_kind,
            "outcome": outcome,
            "attacker_id": self.attacker_id,
            "defender_id": self.defender_id,
            "retreat_distance": retreat_distance,
            "retreat_unit_id": retreat_unit_id,
        }

        st = state
        if outcome == "defender_destroyed":
            st = DeleteUnit(self.defender_id).apply(st)
            self._delete_applied = True
        else:
            self._delete_applied = False

        new_ext = {**st.extension, "hexdemo": hx}
        return st.with_extension(new_ext).with_rng_log(new_rng)

    def revert(self, state: GameState) -> GameState:
        st = state
        if self._delete_applied:
            st = DeleteUnit(self.defender_id).revert(st)
        ext = dict(st.extension)
        ext["hexdemo"] = dict(self._prev_hexdemo) if self._prev_hexdemo is not None else {}
        st = st.with_extension(ext)
        return st.with_rng_log(self._prev_rng_log if self._prev_rng_log is not None else ())

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            f"<Attack {self.attack_kind!r} {self.attacker_id!r} -> {self.defender_id!r}>"
        )
