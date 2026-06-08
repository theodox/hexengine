"""
Hexdemo match configuration — **edit here** to change turn order, factions, and budgets.

The engine calls `hexdemo.registry.build_game_definition`, which builds a
`hexengine.gamedef.protocol.GameDefinition` from `HexdemoMatchConfig`.

Typical changes:

- **Declarative wire** (stack cap, faction labels, highlight CSS, …) —
  `resources/game_data.toml`, referenced from `hexengine_pack.toml` `[gamedata]`.
- **Faction order** — `HEXDEMO_FACTIONS` in `hexdemo.constants` (first side opens
  the round; see `hexengine.gameroot.initial_turn_slot_for_game_definition`).
- **Turn rota** — edit `hexdemo_four_phase_entries` (or replace the
  `StaticScheduleGameDefinition` built in `game_definition_from_config`).
- **Movement preview budget** — set `movement_budget` to match scenario feel.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hexengine.gamedef import unit_attributes as unit_attr_helpers
from hexengine.gamedef.builtin import StaticScheduleGameDefinition
from hexengine.gamedef.game_data import GameData
from hexengine.gamedef.game_data_toml import load_game_data_for_pack_root
from hexengine.gamedef.protocol import GameDefinition
from hexengine.state import DEFAULT_MOVEMENT_BUDGET, GameState

from .combat import transitions as combat_transitions
from .constants import HEXDEMO_FACTIONS
from .hooks import build_hooks
from .ui.focus import focus_unit_id_after_state_sync
from .ui.marker_rules import default_marker_placement_rule

_HEXDEMO_PACK_ROOT = Path(__file__).resolve().parent


def hexdemo_four_phase_entries(
    factions: tuple[str, ...],
) -> tuple[dict[str, Any], ...]:
    """Union Move, Union Combat, Confederate Move, Confederate Combat."""
    if len(factions) < 2:
        raise ValueError("hexdemo four-phase schedule requires two factions")
    union, confederate = factions[0], factions[1]
    return (
        {"faction": union, "phase": "Move", "max_actions": 4},
        {"faction": union, "phase": "Combat", "max_actions": 2},
        {"faction": confederate, "phase": "Move", "max_actions": 4},
        {"faction": confederate, "phase": "Combat", "max_actions": 2},
    )


class HexdemoGameDefinition:
    """
    Wraps a `GameDefinition` with Hexdemo-specific lifecycle hooks.

    Delegates turn geometry to the inner definition.
    """

    __slots__ = ("_base",)

    def __init__(self, base: GameDefinition) -> None:
        self._base = base

    @property
    def game_data(self) -> GameData:
        """Wire-facing title data from `resources/game_data.toml` (see `hexengine_pack.toml`)."""
        return load_game_data_for_pack_root(_HEXDEMO_PACK_ROOT)

    @property
    def hooks(self):
        return build_hooks()

    @property
    def marker_placement_rule(self):
        return default_marker_placement_rule()

    @property
    def _movement_budget(self) -> float:
        """Scalar schedule budget on the inner definition (used by server `turn_rules` wire)."""
        return float(self._base._movement_budget)

    def available_factions(self) -> list[str]:
        return list(self._base.available_factions())

    def turn_order(self) -> list[dict[str, Any]]:
        return self._base.turn_order()

    def get_next_phase(self, state: GameState) -> dict[str, Any]:
        return self._base.get_next_phase(state)

    def focus_unit_id_after_state_sync(
        self, state: GameState, viewer_faction: str | None
    ) -> str | None:
        """Optional hook: which unit the client should select after a state sync."""
        return focus_unit_id_after_state_sync(state, viewer_faction)

    def default_attributes_for_unit_type(self, unit_type: str) -> dict[str, Any]:
        fn = getattr(self._base, "default_attributes_for_unit_type", None)
        if callable(fn):
            return dict(fn(unit_type))
        return unit_attr_helpers.default_attributes_for_unit_type(self._base, unit_type)

    def merge_spawn_attributes(
        self,
        unit_type: str,
        instance_attrs: dict[str, Any],
        state: GameState | None = None,
    ) -> dict[str, Any]:
        fn = getattr(self._base, "merge_spawn_attributes", None)
        if callable(fn):
            return dict(fn(unit_type, dict(instance_attrs or {}), state))
        return unit_attr_helpers.merge_spawn_attributes(
            self._base, unit_type, instance_attrs, state=state
        )

    def validate_unit_attributes_patch(
        self, state: GameState, unit_id: str, patch: dict[str, Any]
    ) -> None:
        fn = getattr(self._base, "validate_unit_attributes_patch", None)
        if callable(fn):
            fn(state, unit_id, patch)
            return
        unit_attr_helpers.validate_unit_attributes_patch(
            self._base, state, unit_id, patch
        )

    def after_phase_transition(self, state: GameState) -> list:
        """
        Called by the server after each `NextPhase` is applied.

        Returns title-owned `StateAction`s for the engine to execute. Hexdemo clears
        its own phase-scoped combat bookkeeping here (the engine does not know these
        bucket keys).
        """
        return combat_transitions.clear_combat_state_actions(state)


@dataclass(frozen=True, slots=True)
class HexdemoMatchConfig:
    """Title-owned settings for one match (authoritative server + thin clients)."""

    factions: tuple[str, ...] = HEXDEMO_FACTIONS
    movement_budget: float = DEFAULT_MOVEMENT_BUDGET


def game_definition_from_config(config: HexdemoMatchConfig) -> GameDefinition:
    """Return a fresh `GameDefinition` for `config` (single static four-phase rota)."""
    base = StaticScheduleGameDefinition(
        hexdemo_four_phase_entries(config.factions),
        movement_budget=config.movement_budget,
    )
    return HexdemoGameDefinition(base)


def default_match_config() -> HexdemoMatchConfig:
    """Default factions and movement budget for the shipped rota."""
    return HexdemoMatchConfig()
