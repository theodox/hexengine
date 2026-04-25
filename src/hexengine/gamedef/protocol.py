"""Protocol for title-specific rules (turn order, factions) hosted by the engine."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..state import GameState


@runtime_checkable
class GameDefinition(Protocol):
    """
    Title-specific rules consulted by GameServer (turn schedule, factions).

    Implementations should be stateless regarding *match* data; do not store
    per-match state on `self` (derive from `hexengine.state.game_state.GameState`
    or inject closures when a title needs session-scoped behavior).

    Optional (for authoritative move validation): `movement_budget_for_unit(state, unit_id)`
    returning the movement cost budget for that unit this phase. Implementations that
    resolve the unit from `state` should raise `ValueError` if `unit_id` is not on the
    board. If absent, the server uses `hexengine.state.logic.DEFAULT_MOVEMENT_BUDGET`.

    Optional (zone of control, stop-on-entry movement): ``zoc_hexes_for_unit(state, unit_id)
    -> frozenset[Hex] | None``. If absent or returns ``None``, moves use reachability
    without ZOC. Otherwise the set is passed to ``hexengine.state.logic`` helpers
    (same rule for retreat destinations when the title supplies ZOC).

    Optional (for ``Attack`` actions): ``validate_attack_request(
        state, *, player_faction: str, attack_kind: str, params: dict
    ) -> None`` — raise ``ValueError`` if the attack is illegal for this title
    (wrong phase, not adjacent when ``attack_kind == "adjacent"``, etc.).
    If absent, the server rejects ``Attack`` requests for that title.

    Optional (after a successful ``Attack``): ``should_auto_advance_phase_after_attack(state) -> bool``.
    If present and returns True, ``GameServer`` immediately applies ``NextPhase`` (same path as
    manual advance). Titles use this e.g. when every active unit of ``state.turn.current_faction``
    has used its combat-segment attack and no retreat obligation remains.

    Optional (retreat / obligation UX, title-defined extension layout):

    - ``retreat_obligation_hexes_remaining(state, unit_id) -> int | None``
    - ``any_retreat_obligation_pending(state) -> bool``
    - ``faction_has_pending_retreat_obligation(state, faction: str) -> bool``

    If absent, the server treats every unit as having no retreat obligation.

    Optional (per-unit ``UnitState.attributes``, title-defined JSON-safe data):

    - ``default_attributes_for_unit_type(unit_type: str) -> dict[str, Any]``
    - ``merge_spawn_attributes(unit_type: str, instance_attrs: dict[str, Any], state: GameState | None) -> dict[str, Any]``
    - ``validate_unit_attributes_patch(state: GameState, unit_id: str, patch: dict[str, Any]) -> None``

    If omitted, built-in definitions use empty defaults / merge / no-op validation.

    Optional (per-viewer focus hint, title policy; consumed via ``StateUpdate``):

    - ``focus_unit_id_after_state_sync(state, viewer_faction: str | None) -> str | None``

    When present, ``GameServer`` copies the result into
    ``StateUpdate.suggested_focus_unit_id`` for that viewer on each state broadcast.
    The browser ``Game`` applies that field only (it does not call this hook).
    """

    def available_factions(self) -> list[str]:
        """Factions players may join as (order may matter for UI)."""
        ...

    def turn_order(self) -> list[dict[str, Any]]:
        """
        Flat turn schedule: each entry has keys `faction`, `phase`, `max_actions`.
        """
        ...

    def get_next_phase(self, state: GameState) -> dict[str, Any]:
        """
        Next schedule slot after the current `state.turn.schedule_index` (wraps).

        Return value includes `faction`, `phase`, `max_actions`, and
        `schedule_index` (the index of the next slot in `turn_order()`).
        """
        ...
