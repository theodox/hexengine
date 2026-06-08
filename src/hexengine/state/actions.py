"""
State-based actions for the immutable state system.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from ..hexes.types import Hex
from ..snapshot import (
    assert_snapshot_json_serializable,
    normalize_snapshot_mapping,
    normalize_snapshot_value,
)
from .action_manager import StateAction
from .game_state import TurnState
from .movement_arc import (
    HEXENGINE_MOVEMENT_ARC_KEY,
    MOVEMENT_ARC_GATE_AWAITING_CONTINUE,
    MOVEMENT_ARC_GATE_AWAITING_INTERRUPT,
    turn_state_from_movement_arc_snapshot,
)

if TYPE_CHECKING:
    from ..state.game_state import GameState, UnitState

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
        si = state.board.next_stack_index_at_hex(
            self.to_hex, exclude_unit_id=self.unit_id
        )
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


class SetTurnState(StateAction):
    """Replace `GameState.turn` (used for movement interrupt handoffs)."""

    def __init__(self, new_turn: TurnState):
        self.new_turn = new_turn
        self._prev_turn: TurnState | None = None

    def apply(self, state: GameState) -> GameState:
        self._prev_turn = state.turn
        return state.with_turn(self.new_turn)

    def revert(self, state: GameState) -> GameState:
        if self._prev_turn is None:
            return state
        return state.with_turn(self._prev_turn)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<SetTurnState {self.new_turn!r}>"


class WriteHexengineMovementArc(StateAction):
    """Write or clear `extension[HEXENGINE_MOVEMENT_ARC_KEY]` (movement **arc** state)."""

    def __init__(self, payload: dict[str, Any] | None):
        self.payload = payload
        self._had_key = False
        self._prev_value: Any = None

    def apply(self, state: GameState) -> GameState:
        from .engine_session_state import with_engine_bucket

        self._had_key = HEXENGINE_MOVEMENT_ARC_KEY in state.engine_state
        self._prev_value = state.engine_state.get(HEXENGINE_MOVEMENT_ARC_KEY)
        if self.payload is None:
            es = dict(state.engine_state)
            es.pop(HEXENGINE_MOVEMENT_ARC_KEY, None)
            return state.with_engine_state(es)
        return with_engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY, dict(self.payload))

    def revert(self, state: GameState) -> GameState:
        from .engine_session_state import with_engine_bucket

        if self._had_key:
            return with_engine_bucket(
                state,
                HEXENGINE_MOVEMENT_ARC_KEY,
                dict(self._prev_value) if isinstance(self._prev_value, dict) else {},
            )
        es = dict(state.engine_state)
        es.pop(HEXENGINE_MOVEMENT_ARC_KEY, None)
        return state.with_engine_state(es)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<WriteHexengineMovementArc {self.payload!r}>"


class ResolvePassMovementInterrupt(StateAction):
    """Finish one **segment** of a movement interrupt queue (see `movement_arc`)."""

    def __init__(self, responding_faction: str):
        self.responding_faction = str(responding_faction).strip()
        self._saved_ext: dict[str, Any] | None = None
        self._saved_turn: TurnState | None = None

    def apply(self, state: GameState) -> GameState:
        from .engine_session_state import engine_bucket, with_engine_bucket

        raw = engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY)
        if not raw:
            raise ValueError("No hexengine movement arc")
        arc = dict(raw)
        if str(arc.get("gate", "")) != MOVEMENT_ARC_GATE_AWAITING_INTERRUPT:
            raise ValueError("Not awaiting movement interrupt")
        q_raw = arc.get("interrupt_queue")
        if not isinstance(q_raw, list) or not q_raw:
            raise ValueError("Movement interrupt queue empty")
        queue = [str(x).strip() for x in q_raw if str(x).strip()]
        if not queue or queue[0] != self.responding_faction:
            raise ValueError("Not your movement interrupt window")

        self._saved_ext = dict(state.engine_state)
        self._saved_turn = state.turn

        rest = queue[1:]
        if not rest:
            snap = arc.get("saved_turn")
            if not isinstance(snap, dict):
                raise ValueError("Movement arc missing saved_turn")
            restored = turn_state_from_movement_arc_snapshot(snap)
            arc["interrupt_queue"] = []
            arc["gate"] = MOVEMENT_ARC_GATE_AWAITING_CONTINUE
            arc["saved_turn"] = None
            return with_engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY, arc).with_turn(
                restored
            )

        next_f = rest[0]
        arc["interrupt_queue"] = rest
        nt = replace(
            state.turn,
            current_faction=next_f,
        )
        return with_engine_bucket(state, HEXENGINE_MOVEMENT_ARC_KEY, arc).with_turn(nt)

    def revert(self, state: GameState) -> GameState:
        if self._saved_ext is None or self._saved_turn is None:
            return state
        return state.with_engine_state(self._saved_ext).with_turn(self._saved_turn)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<ResolvePassMovementInterrupt {self.responding_faction!r}>"


class PatchUnitAttributes(StateAction):
    """Shallow-merge keys into UnitState.attributes (title-defined JSON-safe data)."""

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


class ApplyBucketPatch(StateAction):
    """Apply a ``BucketPatch`` to a pack session-state bucket (undo restores prior snapshot)."""

    def __init__(self, session_state_key: str, patch: BucketPatch) -> None:
        from .engine_session_state import BucketPatch

        self.session_state_key = str(session_state_key).strip()
        if not self.session_state_key:
            raise ValueError("session_state_key must be non-empty")
        if not isinstance(patch, BucketPatch):
            raise TypeError("patch must be a BucketPatch")
        self.patch = patch
        self._saved_bucket: dict[str, Any] | None = None

    def apply(self, state: GameState) -> GameState:
        from .engine_session_state import engine_read_session_state, engine_write_session_state

        prior = engine_read_session_state(state, self.session_state_key)
        self._saved_bucket = dict(prior)
        new_hx = {**prior, **dict(self.patch.values)}
        for k in self.patch.remove_keys:
            new_hx.pop(k, None)
        return engine_write_session_state(state, self.session_state_key, new_hx)

    def revert(self, state: GameState) -> GameState:
        if self._saved_bucket is None:
            return state
        from .engine_session_state import engine_write_session_state

        return engine_write_session_state(state, self.session_state_key, self._saved_bucket)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"<ApplyBucketPatch {self.session_state_key!r}>"


class ClearUnitRetreatObligation(StateAction):
    """Clear one unit's entry from title retreat_obligations after a fulfillment move."""

    def __init__(self, unit_id: str, session_state_key: str) -> None:
        self.unit_id = unit_id
        self.session_state_key = session_state_key
        self._inner: ApplyBucketPatch | None = None

    def apply(self, state: GameState) -> GameState:
        from .engine_session_state import engine_read_session_state

        hx = engine_read_session_state(state, self.session_state_key)
        if not hx:
            self._inner = None
            return state
        ro = dict(hx.get("retreat_obligations", {}))
        if self.unit_id not in ro:
            self._inner = None
            return state
        ro.pop(self.unit_id, None)
        from .engine_session_state import BucketPatch

        self._inner = ApplyBucketPatch(
            self.session_state_key,
            BucketPatch(values={"retreat_obligations": ro}),
        )
        return self._inner.apply(state)

    def revert(self, state: GameState) -> GameState:
        if self._inner is None:
            return state
        return self._inner.revert(state)

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            f"<ClearUnitRetreatObligation {self.unit_id!r} "
            f"session_state_key={self.session_state_key!r}>"
        )


def _retreat_obligations_have_pending(ro: dict[str, Any]) -> bool:
    for v in ro.values():
        try:
            if int(v) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _unit_type_is_infantry(unit: UnitState) -> bool:
    """Hexdemo-style two-step cadence applies to `unit_type` `infantry` only."""
    return str(unit.unit_type).strip().lower() == "infantry"


def _int_attr(attrs: dict[str, Any], key: str, default: int = 0) -> int:
    raw = attrs.get(key, default)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _graphics_template_key_for_step(
    attrs: dict[str, Any], *, step_index: int
) -> str | None:
    """Return `[[unit_graphics]]` `type` from `attributes['steps'][step_index].graphics`."""
    raw = attrs.get("steps")
    if not isinstance(raw, list) or step_index < 0 or step_index >= len(raw):
        return None
    row = raw[step_index]
    if not isinstance(row, dict):
        return None
    g = row.get("graphics")
    if isinstance(g, str):
        s = g.strip()
        if s:
            return s
    return None


def _step1_patch_from_explicit_steps(attrs: dict[str, Any]) -> dict[str, Any] | None:
    """
    Optional explicit step table in unit attributes:

        steps = [ { combat=..., morale=... }, { combat=..., morale=... }, ... ]

    On first step loss we apply step index 1 values when present.
    """
    raw = attrs.get("steps")
    if not isinstance(raw, list) or len(raw) < 2:
        return None
    step1 = raw[1]
    if not isinstance(step1, dict):
        return None
    patch: dict[str, Any] = {}
    if "combat" in step1:
        try:
            patch["combat"] = max(0, int(step1["combat"]))
        except (TypeError, ValueError):
            pass
    if "morale" in step1:
        try:
            patch["morale"] = max(0, int(step1["morale"]))
        except (TypeError, ValueError):
            pass
    return patch or None


def _apply_step_loss_to_unit(state: GameState, unit_id: str) -> GameState:
    """Apply one combat step loss: infantry drops combat/morale on first loss; then delete.

    - **Infantry** (`unit_type` `infantry`, case-insensitive): first loss sets
      `steps_lost` to 1 and reduces `combat` and `morale` by 1 each (floor 0);
      movement and other attributes are unchanged. A second loss applies
      `DeleteUnit` (unit deactivated).
    - **Other types**: first loss only sets `steps_lost` to 1; second loss applies
      `DeleteUnit` (no automatic combat/morale change on the first loss).
    - If `attributes['steps'][1].graphics` is set, first loss also updates
      `UnitState.graphics` so clients swap `[[unit_graphics]]` templates.
    """
    unit = state.board.units.get(unit_id)
    if unit is None or not unit.active:
        return state
    raw = unit.attributes.get("steps_lost", 0)
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        patch: dict[str, Any] = {"steps_lost": 1}
        if _unit_type_is_infantry(unit):
            explicit = _step1_patch_from_explicit_steps(unit.attributes)
            if explicit is not None:
                patch.update(explicit)
            else:
                c = _int_attr(unit.attributes, "combat", 0)
                m = _int_attr(unit.attributes, "morale", 0)
                patch["combat"] = max(0, c - 1)
                patch["morale"] = max(0, m - 1)
        st = PatchUnitAttributes(unit_id, patch).apply(state)
        u2 = st.board.units.get(unit_id)
        if u2 is not None and u2.active:
            gkey = _graphics_template_key_for_step(u2.attributes, step_index=1)
            if gkey is not None and gkey != u2.graphics:
                st = st.with_board(st.board.with_unit(u2.with_graphics(gkey)))
        return st
    return DeleteUnit(unit_id).apply(state)


class ApplyCombatEffects(StateAction):
    """Apply title `AttackResolution.effects` after the core `Attack` state action.

    `effects` is normalized to a JSON-safe snapshot tree in `__init__` (nested
    dataclasses expanded); titles should not call snapshot helpers themselves.
    """

    def __init__(self, effects: dict[str, Any]) -> None:
        self.effects = normalize_snapshot_mapping(effects)
        assert_snapshot_json_serializable(
            self.effects, context=" (ApplyCombatEffects.effects)"
        )

    def apply(self, state: GameState) -> GameState:
        st = state
        eff = self.effects
        if not eff:
            return state

        step_rows = eff.get("step_losses")
        if isinstance(step_rows, list):
            for row in step_rows:
                if isinstance(row, dict):
                    uid = str(row.get("unit_id", "")).strip()
                    try:
                        count = int(row.get("count", 1))
                    except (TypeError, ValueError):
                        count = 1
                elif isinstance(row, str) and row.strip():
                    uid, count = row.strip(), 1
                else:
                    continue
                if not uid:
                    continue
                for _ in range(max(count, 1)):
                    st = _apply_step_loss_to_unit(st, uid)

        disrupt = eff.get("disrupt")
        if isinstance(disrupt, list):
            seen: set[str] = set()
            for item in disrupt:
                uid = str(item).strip() if isinstance(item, str) else ""
                if not uid or uid in seen:
                    continue
                seen.add(uid)
                u0 = st.board.units.get(uid)
                if u0 is None or not u0.active:
                    continue
                for u in st.board.active_units_at_hex(u0.position):
                    if u.faction != u0.faction:
                        continue
                    st = PatchUnitAttributes(str(u.unit_id), {"disrupted": True}).apply(
                        st
                    )
        return st

    def revert(self, state: GameState) -> GameState:
        return state

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "<ApplyCombatEffects>"


class Attack(StateAction):
    """Single attack action (attack_kind dispatches; title decides legality/outcome).

    Titles may resolve an attack against multiple attackers and/or defenders via
    `attacker_ids` / `defender_ids`. Defenders may occupy multiple hexes; extension
    `last_combat` records both a primary `defender_hex` and `defender_hexes`.
    """

    def __init__(
        self,
        attack_kind: str,
        attacker_id: str,
        defender_id: str,
        *,
        outcome: str,
        attacker_ids: tuple[str, ...] | None = None,
        defender_ids: tuple[str, ...] | None = None,
        retreat_distance: int | None = None,
        retreat_unit_id: str | None = None,
        rng_entry: dict[str, Any] | None = None,
    ) -> None:
        self.attack_kind = attack_kind
        self.attacker_id = attacker_id
        self.defender_id = defender_id
        self.outcome = outcome
        if attacker_ids is None:
            self.attacker_ids: tuple[str, ...] | None = None
        else:
            norm_a: list[str] = []
            seen_a: set[str] = set()
            for uid in attacker_ids:
                if not isinstance(uid, str):
                    continue
                s = uid.strip()
                if not s or s in seen_a:
                    continue
                seen_a.add(s)
                norm_a.append(s)
            self.attacker_ids = tuple(norm_a) if norm_a else None
        if defender_ids is None:
            self.defender_ids: tuple[str, ...] | None = None
        else:
            norm: list[str] = []
            seen: set[str] = set()
            for uid in defender_ids:
                if not isinstance(uid, str):
                    continue
                s = uid.strip()
                if not s or s in seen:
                    continue
                seen.add(s)
                norm.append(s)
            self.defender_ids = tuple(norm) if norm else None
        self.retreat_distance = retreat_distance
        self.retreat_unit_id = str(retreat_unit_id) if retreat_unit_id else None
        if rng_entry is None:
            self.rng_entry = None
        else:
            n = normalize_snapshot_value(rng_entry)
            if not isinstance(n, dict):
                raise TypeError(
                    "rng_entry must be a mapping or a dataclass that normalizes to a dict"
                )
            assert_snapshot_json_serializable(n, context=" (Attack.rng_entry)")
            self.rng_entry = n
        self._prev_extension_bucket: dict[str, Any] | None = None
        self._prev_rng_log: tuple[dict[str, Any], ...] | None = None
        self._deleted_unit_ids: tuple[str, ...] = ()

    def apply(self, state: GameState) -> GameState:
        attacker_ids = self.attacker_ids or (self.attacker_id,)
        attackers = []
        for aid in attacker_ids:
            a = state.board.units.get(aid)
            if a is None or not a.active:
                raise ValueError(f"Attacker {aid!r} not found or inactive")
            attackers.append(a)
        attacker0 = attackers[0]

        defender_ids = self.defender_ids or (self.defender_id,)
        defenders = []
        for did in defender_ids:
            d = state.board.units.get(did)
            if d is None or not d.active:
                raise ValueError(f"Defender {did!r} not found or inactive")
            if attacker0.faction == d.faction:
                raise ValueError("Cannot attack same faction")
            defenders.append(d)
        defenders[0]
        tuple(
            sorted(
                {d.position for d in defenders},
                key=lambda h: (int(h.i), int(h.j), int(h.k)),
            )
        )
        tuple(
            sorted(
                {a.position for a in attackers},
                key=lambda h: (int(h.i), int(h.j), int(h.k)),
            )
        )

        self._prev_rng_log = state.rng_log

        outcome = str(self.outcome)
        retreat_distance = self.retreat_distance
        if (
            outcome in ("attacker_retreat", "defender_retreat")
            and retreat_distance is None
        ):
            raise ValueError("retreat_distance is required for retreat outcomes")
        if outcome not in (
            "none",
            "attacker_retreat",
            "defender_retreat",
            "defender_destroyed",
        ):
            raise ValueError(f"Unknown attack outcome {outcome!r}")

        new_rng = state.rng_log
        if self.rng_entry is not None:
            new_rng = new_rng + (dict(self.rng_entry),)

        st = state
        if outcome == "defender_destroyed":
            deleted: list[str] = []
            for d in defenders:
                st = DeleteUnit(d.unit_id).apply(st)
                deleted.append(d.unit_id)
            self._deleted_unit_ids = tuple(deleted)
        else:
            self._deleted_unit_ids = ()

        return st.with_rng_log(new_rng)

    def revert(self, state: GameState) -> GameState:
        st = state
        if self._deleted_unit_ids:
            for uid in self._deleted_unit_ids:
                st = DeleteUnit(uid).revert(st)
        return st.with_rng_log(
            self._prev_rng_log if self._prev_rng_log is not None else ()
        )

    def should_revert_prior(self) -> bool:
        return False

    def __repr__(self) -> str:
        return (
            f"<Attack {self.attack_kind!r} {self.attacker_id!r} -> {self.defender_id!r} "
            f"outcome={self.outcome!r}>"
        )
