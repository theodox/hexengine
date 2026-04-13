"""
Hexdemo match configuration — **edit here** to change turn order, factions, and budgets.

The engine calls `hexdemo.registry.build_game_definition`, which builds a
`hexengine.gamedef.protocol.GameDefinition` from `HexdemoMatchConfig`.

Typical changes:

- **Faction order** — `HEXDEMO_FACTIONS` in `hexdemo.constants` (first side opens
  the round; see `hexengine.gameroot.initial_turn_slot_for_game_definition`).
- **Default vs sequential** — `schedule` (`interleaved` / `default` use the four-phase
  Union/Confederate Move/Combat rota; `sequential` uses Movement/Attack blocks).
- **Movement preview budget** — set `movement_budget` to match scenario feel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from hexengine.gamedef.builtin import (
    SequentialTwoFactionGameDefinition,
    StaticScheduleGameDefinition,
)
from hexengine.gamedef.protocol import GameDefinition
from hexengine.state import DEFAULT_MOVEMENT_BUDGET, GameState
from hexengine.state.phase_rules import phase_allows_unit_move

from .constants import HEXDEMO_FACTIONS

Schedule = Literal["interleaved", "sequential"]


def hexdemo_four_phase_entries(
    factions: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Union Move, Union Combat, Confederate Move, Confederate Combat."""
    if len(factions) < 2:
        raise ValueError("hexdemo four-phase schedule requires two factions")
    union_side, confed_side = factions[0], factions[1]
    return (
        {"faction": union_side, "phase": "Move", "max_actions": 2},
        {"faction": union_side, "phase": "Combat", "max_actions": 2},
        {"faction": confed_side, "phase": "Move", "max_actions": 2},
        {"faction": confed_side, "phase": "Combat", "max_actions": 2},
    )


class HexdemoGameDefinition:
    """
    Wraps a `GameDefinition` with Hexdemo-specific lifecycle hooks.

    Delegates turn geometry to the inner definition.
    """

    __slots__ = ("_base",)

    def __init__(self, base: GameDefinition) -> None:
        self._base = base

    def available_factions(self) -> list[str]:
        return self._base.available_factions()

    def turn_order(self) -> list[dict[str, Any]]:
        return self._base.turn_order()

    def get_next_phase(self, state: GameState) -> dict[str, Any]:
        return self._base.get_next_phase(state)

    def movement_budget_for_unit(self, state: GameState, unit_id: str) -> float:
        fn = getattr(self._base, "movement_budget_for_unit", None)
        if callable(fn):
            return float(fn(state, unit_id))
        return float(DEFAULT_MOVEMENT_BUDGET)

    def after_phase_transition(self, state: GameState) -> None:
        """Called by the server after each `NextPhase` is applied."""
        from .turn_hooks import before_union_move

        t = state.turn
        if t.current_faction == "union" and phase_allows_unit_move(t.current_phase):
            before_union_move(state)


@dataclass(frozen=True, slots=True)
class HexdemoMatchConfig:
    """
    Title-owned settings for one match (authoritative server + thin clients).

    `schedule` `interleaved` (and registry `default`) use the four-phase rota.
    `sequential` uses classic Movement/Attack per faction (IGOUGO).
    """

    schedule: Schedule
    factions: tuple[str, ...] = HEXDEMO_FACTIONS
    movement_budget: float = DEFAULT_MOVEMENT_BUDGET

    @classmethod
    def from_registry_key(cls, key: str) -> HexdemoMatchConfig:
        """
        Map `hexdemo.registry.build_game_definition` ids to a config.

        Keys: `default` / `interleaved` → four-phase rota; `sequential` → Movement/Attack sequential.
        """
        k = key.strip().lower()
        if k in ("default", "interleaved"):
            return cls(schedule="interleaved")
        if k == "sequential":
            return cls(schedule="sequential")
        raise KeyError(f"Unknown hexdemo game definition id: {key!r}")


def game_definition_from_config(config: HexdemoMatchConfig) -> GameDefinition:
    """Return a fresh `GameDefinition` for `config`."""
    if config.schedule == "sequential":
        base: GameDefinition = SequentialTwoFactionGameDefinition(
            factions=config.factions,
            movement_budget=config.movement_budget,
        )
    else:
        base = StaticScheduleGameDefinition(
            hexdemo_four_phase_entries(config.factions),
            movement_budget=config.movement_budget,
        )
    return HexdemoGameDefinition(base)


def default_match_config() -> HexdemoMatchConfig:
    """Default four-phase schedule with `hexdemo.constants.HEXDEMO_FACTIONS`."""
    return HexdemoMatchConfig(schedule="interleaved")
