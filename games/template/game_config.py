"""
Template match configuration — start here when cloning this pack.

Uses a declared turn arc registry (Phase 6 authoring patterns) plus a static schedule
fallback on the inner GameDefinition for tooling that still reads turn_order().
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hexengine.gamedef.builtin import StaticScheduleGameDefinition
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
    """Minimal GameDefinition: move-only schedule + arc registry on hooks."""

    __slots__ = ("_base",)

    def __init__(self, base: StaticScheduleGameDefinition) -> None:
        self._base = base

    @property
    def game_data(self) -> GameData:
        return load_game_data_for_pack_root(_PACK_ROOT)

    @property
    def hooks(self):
        from .hooks import build_hooks

        return build_hooks()

    @property
    def _movement_budget(self) -> float:
        return float(self._base._movement_budget)

    def available_factions(self) -> list[str]:
        return list(self._base.available_factions())

    def turn_order(self) -> list[dict]:
        return self._base.turn_order()

    def get_next_phase(self, state: GameState) -> dict:
        return self._base.get_next_phase(state)


def game_definition_from_config(config: TemplateMatchConfig) -> GameDefinition:
    reg = build_template_turn_arc_registry(config.factions)
    base = StaticScheduleGameDefinition(
        reg.schedule.turn_order_entries(),
        movement_budget=float(config.movement_budget),
    )
    return TemplateGameDefinition(base)


__all__ = [
    "TemplateGameDefinition",
    "TemplateMatchConfig",
    "default_match_config",
    "game_definition_from_config",
]
