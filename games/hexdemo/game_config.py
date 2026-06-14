"""
Hexdemo match configuration — **edit here** to change factions and movement budget.

The engine calls `hexdemo.registry.build_game_definition`, which builds a
`hexengine.gamedef.protocol.GameDefinition` from `HexdemoMatchConfig`.

Typical changes:

- **Declarative wire** (stack cap, faction labels, highlight CSS, …) —
  `resources/game_data.toml`, referenced from `hexengine_pack.toml` `[gamedata]`.
- **Faction order** — `HEXDEMO_FACTIONS` in `hexdemo.constants` (first side opens
  the round; see `hexengine.gameroot.initial_turn_slot_for_game_definition`).
- **Turn rota** — `arcs/turn_schedule.py` (`TurnArcRegistry`); not a parallel
  static schedule table on this class.
- **Movement preview budget** — set `movement_budget` to match scenario feel.

``turn.current_phase`` on the wire remains a display label derived from the
schedule; legality uses the arc cursor and ``current_segment`` (not phase names).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hexengine.gamedef.game_data import GameData
from hexengine.gamedef.game_data_toml import load_game_data_for_pack_root
from hexengine.gamedef.protocol import GameDefinition
from hexengine.state import DEFAULT_MOVEMENT_BUDGET, GameState

from .arcs.turn_schedule import (
    build_hexdemo_turn_arc_registry,
    hexdemo_four_phase_entries,
)
from .combat import transitions as combat_transitions
from .constants import HEXDEMO_FACTIONS
from .hooks import build_hooks
from .ui.focus import focus_unit_id_after_state_sync
from .ui.marker_rules import default_marker_placement_rule

_HEXDEMO_PACK_ROOT = Path(__file__).resolve().parent


class HexdemoGameDefinition:
    """
    Hexdemo match rules: turn rota from ``TurnArcRegistry``, title hooks, lifecycle.

    Turn geometry is declared in ``arcs/turn_schedule.py`` and exposed on
    ``TitleHooks.arcs``; ``turn_order()`` here mirrors that registry for wire and
    contract validation only.
    """

    __slots__ = ("_config",)

    def __init__(self, config: HexdemoMatchConfig) -> None:
        self._config = config

    def _turn_registry(self):
        return build_hexdemo_turn_arc_registry(self._config.factions)

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
        """Scalar schedule budget on the definition (used by server `turn_rules` wire)."""
        return float(self._config.movement_budget)

    def available_factions(self) -> list[str]:
        return self._turn_registry().schedule.available_factions()

    def turn_order(self) -> list[dict[str, Any]]:
        return self._turn_registry().schedule.turn_order_entries()

    def get_next_phase(self, state: GameState) -> dict[str, Any]:
        slot, next_idx = self._turn_registry().schedule.next_after(
            state.turn.schedule_index
        )
        return {
            "faction": slot.faction,
            "phase": slot.phase,
            "max_actions": int(slot.max_actions),
            "schedule_index": next_idx,
        }

    def focus_unit_id_after_state_sync(
        self, state: GameState, viewer_faction: str | None
    ) -> str | None:
        """Optional hook: which unit the client should select after a state sync."""
        return focus_unit_id_after_state_sync(state, viewer_faction)

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
        return {**base, **dict(instance_attrs or {})}

    def validate_unit_attributes_patch(
        self, state: GameState, unit_id: str, patch: dict[str, Any]
    ) -> None:
        _ = state, unit_id, patch

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
    """Return a fresh `GameDefinition` for `config` (registry-backed four-phase rota)."""
    return HexdemoGameDefinition(config)


def default_match_config() -> HexdemoMatchConfig:
    """Default factions and movement budget for the shipped rota."""
    return HexdemoMatchConfig()


__all__ = [
    "HexdemoGameDefinition",
    "HexdemoMatchConfig",
    "default_match_config",
    "game_definition_from_config",
    "hexdemo_four_phase_entries",
]
