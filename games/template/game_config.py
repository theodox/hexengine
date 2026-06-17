"""
Template match configuration — start here when cloning this pack.

Turn rota is declared in ``turn_arc_schedule.py`` and wired on
``TitleHooks.arcs.turn_arc_registry`` from ``hooks.build_hooks``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hexengine.arcs.registry import TurnArcRegistry
from hexengine.gamedef.game_data import GameData
from hexengine.gamedef.game_data_toml import load_game_data_for_pack_root
from hexengine.gamedef.protocol import GameDefinition

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

    __slots__ = ("_config", "_turn_registry")

    def __init__(self, config: TemplateMatchConfig) -> None:
        self._config = config
        self._turn_registry = build_template_turn_arc_registry(config.factions)

    @property
    def turn_registry(self) -> TurnArcRegistry:
        return self._turn_registry

    @property
    def game_data(self) -> GameData:
        return load_game_data_for_pack_root(_PACK_ROOT)

    @property
    def hooks(self):
        from .hooks import build_hooks

        return build_hooks(self._turn_registry)

    @property
    def _movement_budget(self) -> float:
        return float(self._config.movement_budget)


def game_definition_from_config(config: TemplateMatchConfig) -> GameDefinition:
    return TemplateGameDefinition(config)


__all__ = [
    "TemplateGameDefinition",
    "TemplateMatchConfig",
    "default_match_config",
    "game_definition_from_config",
]
