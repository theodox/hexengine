"""
Wire-format serialization for GameState (JSON-safe dicts).

Used by the game server, WebSocket client, and save/load snapshots.
"""

from __future__ import annotations

from typing import Any

from ..hexes.types import Hex
from .game_state import (
    BoardState,
    GameState,
    LocationState,
    TurnState,
    UnitState,
    UnsetTerrainDefaults,
)

SNAPSHOT_FORMAT_VERSION = 1


def game_state_to_wire_dict(state: GameState) -> dict[str, Any]:
    """
    Serialize GameState into JSON-safe primitives.

    Hex keys in locations are emitted as a list with explicit position objects.
    """
    units: dict[str, dict[str, Any]] = {}
    for unit_id, unit in state.board.units.items():
        uo: dict[str, Any] = {
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
            "stack_index": unit.stack_index,
        }
        if unit.graphics is not None:
            uo["graphics"] = unit.graphics
        if unit.attributes:
            uo["attributes"] = dict(unit.attributes)
        units[unit_id] = uo

    locations: list[dict[str, Any]] = []
    for pos, loc in state.board.locations.items():
        d: dict[str, Any] = {
            "position": {"i": pos.i, "j": pos.j, "k": pos.k},
            "terrain_type": loc.terrain_type,
            "movement_cost": loc.movement_cost,
            "assault_modifier": loc.assault_modifier,
            "ranged_modifier": loc.ranged_modifier,
            "block_los": loc.block_los,
        }
        if loc.hex_color is not None:
            d["hex_color"] = loc.hex_color
        locations.append(d)

    board_payload: dict[str, Any] = {
        "units": units,
        "locations": locations,
    }
    ud = state.board.unset_defaults
    if ud is not None:
        ud_out: dict[str, Any] = {
            "terrain_type": ud.terrain_type,
            "movement_cost": ud.movement_cost,
            "assault_modifier": ud.assault_modifier,
            "ranged_modifier": ud.ranged_modifier,
            "block_los": ud.block_los,
        }
        if ud.hex_color is not None:
            ud_out["hex_color"] = ud.hex_color
        board_payload["unset_defaults"] = ud_out

    out: dict[str, Any] = {
        "board": board_payload,
        "turn": {
            "current_faction": state.turn.current_faction,
            "current_phase": state.turn.current_phase,
            "phase_actions_remaining": state.turn.phase_actions_remaining,
            "turn_number": state.turn.turn_number,
            "schedule_index": state.turn.schedule_index,
            "global_tick": state.turn.global_tick,
        },
    }
    if state.extension:
        out["extension"] = dict(state.extension)
    if state.rng_log:
        out["rng_log"] = list(state.rng_log)
    return out


def game_state_from_wire_dict(state_dict: dict[str, Any]) -> GameState:
    """Reconstruct GameState from a wire dict (raises on malformed data)."""
    units: dict[str, UnitState] = {}
    for unit_id, unit_data in state_dict.get("board", {}).get("units", {}).items():
        pos_data = unit_data["position"]
        raw_attrs = unit_data.get("attributes")
        attrs: dict[str, Any] = dict(raw_attrs) if isinstance(raw_attrs, dict) else {}
        raw_g = unit_data.get("graphics")
        if raw_g is None:
            graphics = None
        else:
            gs = str(raw_g).strip()
            graphics = gs if gs else None
        units[unit_id] = UnitState(
            unit_id=unit_data["unit_id"],
            unit_type=unit_data["unit_type"],
            faction=unit_data["faction"],
            position=Hex(**pos_data),
            health=int(unit_data.get("health", 100)),
            active=unit_data.get("active", True),
            stack_index=int(unit_data.get("stack_index", 0)),
            graphics=graphics,
            attributes=attrs,
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
        raw_hc = loc.get("hex_color")
        hex_color = (
            None if raw_hc is None else (s if (s := str(raw_hc).strip()) else None)
        )
        locations[pos] = LocationState(
            position=pos,
            terrain_type=loc["terrain_type"],
            movement_cost=loc["movement_cost"],
            hex_color=hex_color,
            assault_modifier=float(loc.get("assault_modifier", 0.0)),
            ranged_modifier=float(loc.get("ranged_modifier", 0.0)),
            block_los=bool(loc.get("block_los", True)),
        )

    unset_defaults: UnsetTerrainDefaults | None = None
    raw_ud = state_dict.get("board", {}).get("unset_defaults")
    if isinstance(raw_ud, dict):
        raw_hc = raw_ud.get("hex_color")
        hc_ud = None if raw_hc is None else (s if (s := str(raw_hc).strip()) else None)
        mc = raw_ud["movement_cost"]
        if isinstance(mc, str) and mc.lower() == "inf":
            mc_val = float("inf")
        else:
            mc_val = float(mc)
        unset_defaults = UnsetTerrainDefaults(
            terrain_type=str(raw_ud["terrain_type"]),
            movement_cost=mc_val,
            hex_color=hc_ud,
            assault_modifier=float(raw_ud.get("assault_modifier", 0.0)),
            ranged_modifier=float(raw_ud.get("ranged_modifier", 0.0)),
            block_los=bool(raw_ud.get("block_los", True)),
        )

    board = BoardState(units=units, locations=locations, unset_defaults=unset_defaults)

    turn_data = state_dict.get("turn")
    if not isinstance(turn_data, dict):
        raise ValueError("game_state.turn must be an object")
    for key in ("current_faction", "current_phase", "phase_actions_remaining"):
        if key not in turn_data:
            raise ValueError(f"game_state.turn.{key} is required")
    turn = TurnState(
        turn_number=int(turn_data.get("turn_number", 1)),
        current_faction=str(turn_data["current_faction"]),
        current_phase=str(turn_data["current_phase"]),
        phase_actions_remaining=int(turn_data["phase_actions_remaining"]),
        schedule_index=int(turn_data.get("schedule_index", 0)),
        global_tick=int(turn_data.get("global_tick", 0)),
    )

    ext = state_dict.get("extension")
    extension: dict[str, Any] = dict(ext) if isinstance(ext, dict) else {}

    raw_rng = state_dict.get("rng_log", [])
    if isinstance(raw_rng, dict):
        raw_iter_rng = raw_rng.values()
    else:
        raw_iter_rng = raw_rng
    rng_log: tuple[dict[str, Any], ...] = tuple(
        dict(x) for x in raw_iter_rng if isinstance(x, dict)
    )

    return GameState(board=board, turn=turn, extension=extension, rng_log=rng_log)
