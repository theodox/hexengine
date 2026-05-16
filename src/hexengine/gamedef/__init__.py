"""Game rules host API: turn schedules, RNG helpers, interaction kinds (engine-owned facades)."""

from __future__ import annotations

from .builtin import (
    InterleavedTwoFactionGameDefinition,
    SequentialTwoFactionGameDefinition,
    StaticScheduleGameDefinition,
    advance_turn_action_for_state,
    default_game_definition,
)
from .client_title_data import ClientTitleData
from .game_data import GameData
from .game_data_toml import (
    game_data_from_mapping,
    load_game_data_for_pack_root,
    merged_gamedata_dict_from_manifest,
)
from .interactions import InteractionKind
from .protocol import GameDefinition
from .rng import RngService

__all__ = [
    "ClientTitleData",
    "GameData",
    "GameDefinition",
    "game_data_from_mapping",
    "load_game_data_for_pack_root",
    "merged_gamedata_dict_from_manifest",
    "InteractionKind",
    "InterleavedTwoFactionGameDefinition",
    "RngService",
    "SequentialTwoFactionGameDefinition",
    "StaticScheduleGameDefinition",
    "advance_turn_action_for_state",
    "default_game_definition",
]
