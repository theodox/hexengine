from __future__ import annotations

from .action_manager import ActionManager
from .actions import (
    AddMarker,
    AddUnit,
    Attack,
    ClearHexdemoCombatExtension,
    ClearUnitRetreatObligation,
    DeleteUnit,
    MoveMarker,
    MoveUnit,
    NextPhase,
    PatchUnitAttributes,
    RemoveMarker,
    SpendAction,
)
from .game_state import (
    BoardState,
    GameState,
    LocationState,
    TurnState,
    UnitState,
    UnsetTerrainDefaults,
)
from .logic import (
    DEFAULT_MOVEMENT_BUDGET,
    adjacent_enemy_zoc_hexes,
    adjacent_friendly_zoc_hexes,
    compute_reachable_hexes,
    compute_retreat_destination_hexes,
    compute_valid_moves,
    is_valid_move,
    retreat_impassable_enemy_zoc_hexes,
)
from .marker_placement import (
    MarkerPlacementRule,
    default_marker_destination_allowed,
    marker_destination_hexes_for_preview,
)
from .snapshot import (
    SNAPSHOT_FORMAT_VERSION,
    game_state_from_wire_dict,
    game_state_to_wire_dict,
)

__all__ = [
    "SNAPSHOT_FORMAT_VERSION",
    "game_state_from_wire_dict",
    "game_state_to_wire_dict",
    "GameState",
    "BoardState",
    "UnitState",
    "LocationState",
    "UnsetTerrainDefaults",
    "TurnState",
    "ActionManager",
    "MoveUnit",
    "Attack",
    "ClearHexdemoCombatExtension",
    "ClearUnitRetreatObligation",
    "MoveMarker",
    "AddMarker",
    "RemoveMarker",
    "DeleteUnit",
    "AddUnit",
    "SpendAction",
    "NextPhase",
    "PatchUnitAttributes",
    "DEFAULT_MOVEMENT_BUDGET",
    "adjacent_enemy_zoc_hexes",
    "adjacent_friendly_zoc_hexes",
    "compute_reachable_hexes",
    "compute_valid_moves",
    "is_valid_move",
    "compute_retreat_destination_hexes",
    "retreat_impassable_enemy_zoc_hexes",
    "MarkerPlacementRule",
    "default_marker_destination_allowed",
    "marker_destination_hexes_for_preview",
]
