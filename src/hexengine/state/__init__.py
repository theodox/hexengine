from __future__ import annotations

from .action_manager import ActionManager
from .actions import (
    AddMarker,
    AddUnit,
    DeleteUnit,
    MoveMarker,
    MoveUnit,
    NextPhase,
    RemoveMarker,
    SpendAction,
)
from .game_state import BoardState, GameState, LocationState, TurnState, UnitState
from .marker_placement import (
    MarkerPlacementRule,
    default_marker_destination_allowed,
    marker_destination_hexes_for_preview,
)
from .logic import compute_reachable_hexes, compute_valid_moves, is_valid_move
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
    "TurnState",
    "ActionManager",
    "MoveUnit",
    "MoveMarker",
    "AddMarker",
    "RemoveMarker",
    "DeleteUnit",
    "AddUnit",
    "SpendAction",
    "NextPhase",
    "compute_reachable_hexes",
    "compute_valid_moves",
    "is_valid_move",
    "MarkerPlacementRule",
    "default_marker_destination_allowed",
    "marker_destination_hexes_for_preview",
]
