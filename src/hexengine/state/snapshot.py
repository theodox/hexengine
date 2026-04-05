"""
Wire-format serialization for GameState (JSON-safe dicts).

Used by the game server, WebSocket client, and save/load snapshots.
"""

from __future__ import annotations

from typing import Any

from ..hexes.types import Hex
from .game_state import BoardState, GameState, LocationState, TurnState, UnitState

SNAPSHOT_FORMAT_VERSION = 1


def game_state_to_wire_dict(state: GameState) -> dict[str, Any]:
    """
    Serialize GameState into JSON-safe primitives.

    Hex keys in locations are emitted as a list with explicit position objects.
    """
    units: dict[str, dict[str, Any]] = {}
    for unit_id, unit in state.board.units.items():
        units[unit_id] = {
            "unit_id": unit.unit_id,
            "unit_type": unit.unit_type,
            "faction": unit.faction,
            "position": {
                "i": unit.position.i,
                "j": unit.position.j,
                "k": unit.position.k,
            },
            "health": unit.health,
            "active": unit.active,
        }

    locations: list[dict[str, Any]] = []
    for pos, loc in state.board.locations.items():
        locations.append(
            {
                "position": {"i": pos.i, "j": pos.j, "k": pos.k},
                "terrain_type": loc.terrain_type,
                "movement_cost": loc.movement_cost,
            }
        )

    return {
        "board": {
            "units": units,
            "locations": locations,
        },
        "turn": {
            "current_faction": state.turn.current_faction,
            "current_phase": state.turn.current_phase,
            "phase_actions_remaining": state.turn.phase_actions_remaining,
            "turn_number": state.turn.turn_number,
        },
    }


def game_state_from_wire_dict(state_dict: dict[str, Any]) -> GameState:
    """Reconstruct GameState from a wire dict (raises on malformed data)."""
    units: dict[str, UnitState] = {}
    for unit_id, unit_data in state_dict.get("board", {}).get("units", {}).items():
        pos_data = unit_data["position"]
        units[unit_id] = UnitState(
            unit_id=unit_data["unit_id"],
            unit_type=unit_data["unit_type"],
            faction=unit_data["faction"],
            position=Hex(**pos_data),
            health=unit_data["health"],
            active=unit_data.get("active", True),
        )

    locations: dict[Hex, LocationState] = {}
    raw_locations = state_dict.get("board", {}).get("locations", [])
    if isinstance(raw_locations, dict):
        raw_iter = raw_locations.values()
    else:
        raw_iter = raw_locations

    for loc in raw_iter:
        pos_data = loc["position"]
        pos = Hex(**pos_data)
        locations[pos] = LocationState(
            position=pos,
            terrain_type=loc["terrain_type"],
            movement_cost=loc["movement_cost"],
        )

    board = BoardState(units=units, locations=locations)

    turn_data = state_dict.get("turn", {})
    turn = TurnState(
        turn_number=turn_data.get("turn_number", 1),
        current_faction=turn_data.get("current_faction", "Red"),
        current_phase=turn_data.get("current_phase", "Movement"),
        phase_actions_remaining=turn_data.get("phase_actions_remaining", 2),
    )

    return GameState(board=board, turn=turn)
