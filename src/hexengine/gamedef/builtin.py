"""Built-in game definitions: static turn rotas and classic two-faction layouts."""

from __future__ import annotations

from typing import Any

from ..state import GameState
from ..state.actions import NextPhase
from .protocol import GameDefinition


def _normalize_entries(
    entries: tuple[dict[str, Any], ...] | list[dict[str, Any]],
) -> tuple[dict[str, Any], ...]:
    out: list[dict[str, Any]] = []
    for e in entries:
        out.append(
            {
                "faction": str(e["faction"]),
                "phase": str(e["phase"]),
                "max_actions": int(e["max_actions"]),
            }
        )
    return tuple(out)


def expand_interleaved_two_faction(
    factions: tuple[str, ...],
    phases: tuple[tuple[str, int], ...],
) -> tuple[dict[str, Any], ...]:
    """Interleaved: for each phase, each faction (A:a, B:a, A:b, B:b)."""
    rows: list[dict[str, Any]] = []
    for phase_name, max_actions in phases:
        for faction in factions:
            rows.append(
                {
                    "faction": faction,
                    "phase": phase_name,
                    "max_actions": max_actions,
                }
            )
    return tuple(rows)


def expand_sequential_two_faction(
    factions: tuple[str, ...],
    phases: tuple[tuple[str, int], ...],
) -> tuple[dict[str, Any], ...]:
    """Sequential: each faction completes all phases before the next (A:a, A:b, B:a, B:b)."""
    rows: list[dict[str, Any]] = []
    for faction in factions:
        for phase_name, max_actions in phases:
            rows.append(
                {
                    "faction": faction,
                    "phase": phase_name,
                    "max_actions": max_actions,
                }
            )
    return tuple(rows)


class StaticScheduleGameDefinition:
    """
    Authoritative turn schedule from a fixed ordered list of slots.

    Each slot is `{faction, phase, max_actions}`. `get_next_phase` advances
    `schedule_index` by one (wrapping). Immutable rota for the match.
    """

    __slots__ = ("_entries", "_movement_budget", "_per_unit_movement_attribute")

    def __init__(
        self,
        entries: tuple[dict[str, Any], ...] | list[dict[str, Any]],
        movement_budget: float = 4.0,
        *,
        per_unit_movement_attribute: str | None = None,
    ) -> None:
        self._entries = _normalize_entries(entries)
        if not self._entries:
            raise ValueError("turn schedule entries must be non-empty")
        self._movement_budget = float(movement_budget)
        if isinstance(per_unit_movement_attribute, str):
            s = per_unit_movement_attribute.strip()
            self._per_unit_movement_attribute = s or None
        else:
            self._per_unit_movement_attribute = None

    def movement_budget_for_unit(self, state: GameState, unit_id: str) -> float:
        key = self._per_unit_movement_attribute
        if key:
            u = state.board.units.get(unit_id)
            if u is None:
                raise ValueError(f"Unknown unit {unit_id!r}")
            raw = u.attributes.get(key)
            if raw is not None:
                return float(raw)
        _ = state, unit_id
        return self._movement_budget

    def available_factions(self) -> list[str]:
        seen: list[str] = []
        for e in self._entries:
            f = str(e["faction"])
            if f not in seen:
                seen.append(f)
        return seen

    def turn_order(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self._entries]

    def get_next_phase(self, state: GameState) -> dict[str, Any]:
        n = len(self._entries)
        idx = int(state.turn.schedule_index) % n
        next_idx = (idx + 1) % n
        slot = self._entries[next_idx]
        return {
            "faction": slot["faction"],
            "phase": slot["phase"],
            "max_actions": slot["max_actions"],
            "schedule_index": next_idx,
        }

    def default_attributes_for_unit_type(self, unit_type: str) -> dict[str, Any]:
        _ = unit_type
        return {}

    def merge_spawn_attributes(
        self,
        unit_type: str,
        instance_attrs: dict[str, Any],
        state: GameState | None = None,
    ) -> dict[str, Any]:
        _ = state
        base = self.default_attributes_for_unit_type(unit_type)
        return {**base, **instance_attrs}

    def validate_unit_attributes_patch(
        self, state: GameState, unit_id: str, patch: dict[str, Any]
    ) -> None:
        _ = state, unit_id, patch


class InterleavedTwoFactionGameDefinition(StaticScheduleGameDefinition):
    """
    Interleaved phases across factions (each phase for every faction in order).

    Default factions `("Red", "Blue")`; default phases Movement then Attack.
    """

    def __init__(
        self,
        factions: tuple[str, ...] = ("Red", "Blue"),
        phases: tuple[tuple[str, int], ...] = (
            ("Movement", 2),
            ("Attack", 2),
        ),
        movement_budget: float = 4.0,
        *,
        per_unit_movement_attribute: str | None = None,
    ) -> None:
        super().__init__(
            expand_interleaved_two_faction(factions, phases),
            movement_budget=movement_budget,
            per_unit_movement_attribute=per_unit_movement_attribute,
        )


class SequentialTwoFactionGameDefinition(StaticScheduleGameDefinition):
    """
    Each faction completes all phases before the next (IGOUGO-style blocks).
    """

    def __init__(
        self,
        factions: tuple[str, ...] = ("Red", "Blue"),
        phases: tuple[tuple[str, int], ...] = (
            ("Movement", 2),
            ("Attack", 2),
        ),
        movement_budget: float = 4.0,
        *,
        per_unit_movement_attribute: str | None = None,
    ) -> None:
        super().__init__(
            expand_sequential_two_faction(factions, phases),
            movement_budget=movement_budget,
            per_unit_movement_attribute=per_unit_movement_attribute,
        )


_DEFAULT_INTERLEAVED: InterleavedTwoFactionGameDefinition | None = None


def default_game_definition() -> InterleavedTwoFactionGameDefinition:
    """Singleton interleaved Red/Blue demo schedule (legacy server behavior)."""
    global _DEFAULT_INTERLEAVED
    if _DEFAULT_INTERLEAVED is None:
        _DEFAULT_INTERLEAVED = InterleavedTwoFactionGameDefinition()
    return _DEFAULT_INTERLEAVED


def advance_turn_action_for_state(state: GameState, game: GameDefinition) -> NextPhase:
    """Build `NextPhase` for the slot after `state.turn` (client/server aligned)."""
    info = game.get_next_phase(state)
    return NextPhase(
        new_faction=info["faction"],
        new_phase=info["phase"],
        max_actions=info["max_actions"],
        new_schedule_index=int(info["schedule_index"]),
    )
