"""Protocol for title-specific match rules (turn order, factions) hosted by the engine."""

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

    Rule customization (movement/combat/stacking/ZOC/etc.) is provided via a hooks bundle:

    - `hexengine.hooks.TitleHooks`
    - Exposed by the game definition as either `hooks` (attribute) or `hooks()` (callable)

    The engine uses only hooks (plus engine defaults when a hook returns `hooks.DEFAULT`).

    Optional: ``title_state_extension_key`` — class attribute or plain ``str`` on the
    definition naming the ``GameState.extension`` bucket used for title-owned combat
    and retreat data (for example the string ``hexdemo``). When set, the server publishes it
    in ``StateUpdate.turn_rules`` and runs phase/combat housekeeping against that key.
    Built-in schedules omit it.

    Phase auto-advance after combat is provided via `TitleHooks` (attack hooks).

    Retreat / obligation UX is also provided via `TitleHooks` (movement hooks).

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
