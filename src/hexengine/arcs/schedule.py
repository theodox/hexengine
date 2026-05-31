"""
Declared turn schedule as a sequence of routine arc slots (composable arcs, Phase 4).

Replaces the flat `turn_order()` rota with an ordered list of schedule slots. Each slot
names a routine phase arc, the acting faction, wire phase label, and action budget.
`get_next_phase` and `turn_order()` derive from this sequence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ScheduleSlot:
    """One position in the match turn rota, bound to a routine phase arc."""

    routine_arc_id: str
    faction: str
    phase: str
    max_actions: int
    kind: str = "routine"


@dataclass(frozen=True, slots=True)
class ArcSchedule:
    """Immutable ordered turn rota: slot index is `TurnState.schedule_index`."""

    slots: tuple[ScheduleSlot, ...]

    def __post_init__(self) -> None:
        if not self.slots:
            raise ValueError("ArcSchedule requires at least one slot")

    def slot_at(self, schedule_index: int) -> ScheduleSlot:
        """Return the slot at `schedule_index` (wraps)."""

        return self.slots[int(schedule_index) % len(self.slots)]

    def next_after(self, schedule_index: int) -> tuple[ScheduleSlot, int]:
        """Return the slot after `schedule_index` and its index (wraps)."""

        n = len(self.slots)
        idx = int(schedule_index) % n
        next_idx = (idx + 1) % n
        return self.slots[next_idx], next_idx

    def turn_order_entries(self) -> list[dict[str, Any]]:
        """Flat rota entries compatible with legacy `GameDefinition.turn_order()`."""

        return [
            {
                "faction": s.faction,
                "phase": s.phase,
                "max_actions": int(s.max_actions),
            }
            for s in self.slots
        ]

    def available_factions(self) -> list[str]:
        """Stable de-dupe of faction ids appearing in the schedule."""

        seen: set[str] = set()
        out: list[str] = []
        for s in self.slots:
            f = str(s.faction).strip()
            if not f or f in seen:
                continue
            seen.add(f)
            out.append(f)
        return out


__all__ = ["ArcSchedule", "ScheduleSlot"]
