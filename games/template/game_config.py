"""
Template match configuration — start here when cloning this pack.

Turn rota is declared in ``turn_arc_schedule.py`` (``TurnArcRegistry`` on hooks).
``turn_order()`` and ``get_next_phase()`` derive from that registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hexengine.gamedef.game_data import GameData
from hexengine.gamedef.game_data_toml import load_game_data_for_pack_root
from hexengine.gamedef.protocol import GameDefinition
from hexengine.state import GameState

from .constants import TEMPLATE_FACTIONS
from .turn_arc_schedule import build_template_turn_arc_registry

_PACK_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class TemplateMatchConfig:
    factions: tuple[str, ...] = TEMPLATE_FACTIONS
    movement_budget: float = 4.0


def default_match_config() -> TemplateMatchConfig:
    return TemplateMatchConfig()


class TemplateGameDefinition:
    """Minimal GameDefinition: move-only schedule from ``TurnArcRegistry``."""

    __slots__ = ("_config",)

    def __init__(self, config: TemplateMatchConfig) -> None:
        self._config = config

    def _turn_registry(self):
        return build_template_turn_arc_registry(self._config.factions)

    @property
    def game_data(self) -> GameData:
        return load_game_data_for_pack_root(_PACK_ROOT)

    @property
    def hooks(self):
        from .hooks import build_hooks

        return build_hooks()

    @property
    def _movement_budget(self) -> float:
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


def game_definition_from_config(config: TemplateMatchConfig) -> GameDefinition:
    return TemplateGameDefinition(config)


__all__ = [
    "TemplateGameDefinition",
    "TemplateMatchConfig",
    "default_match_config",
    "game_definition_from_config",
]
