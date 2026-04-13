"""Game rules host API: turn schedules, RNG helpers, interaction kinds (engine-owned facades)."""

from __future__ import annotations

from .builtin import (
    InterleavedTwoFactionGameDefinition,
    SequentialTwoFactionGameDefinition,
    StaticScheduleGameDefinition,
    advance_turn_action_for_state,
    default_game_definition,
)
from .faction_display import display_faction_name, display_phase_name
from .interactions import InteractionKind
from .protocol import GameDefinition
from .rng import RngService

__all__ = [
    "GameDefinition",
    "display_faction_name",
    "display_phase_name",
    "InteractionKind",
    "InterleavedTwoFactionGameDefinition",
    "RngService",
    "SequentialTwoFactionGameDefinition",
    "StaticScheduleGameDefinition",
    "advance_turn_action_for_state",
    "default_game_definition",
]
