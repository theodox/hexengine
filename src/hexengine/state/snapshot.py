"""
Wire-format serialization for GameState (JSON-safe dicts).

Used by the game server, WebSocket client, and save/load snapshots.
"""

from __future__ import annotations

from typing import Any

from ..hexes.centerline import validate_linear_hex_path
from ..hexes.edges import EdgeKey
from ..hexes.types import Hex
from ..wire_interop import wire_str
from .game_state import (
    BoardEdgeFeature,
    BoardLinearFeature,
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

    def _hex_wire(h: Hex) -> dict[str, int]:
        return {"i": h.i, "j": h.j, "k": h.k}

    def _edge_key_wire(ek: EdgeKey) -> dict[str, Any]:
        return {"hex_low": _hex_wire(ek.hex_low), "hex_high": _hex_wire(ek.hex_high)}

    if state.board.edge_features:
        ef_out: list[dict[str, Any]] = []
        for f in state.board.edge_features:
            row: dict[str, Any] = {
                "feature_id": f.feature_id,
                "edge_key": _edge_key_wire(f.edge_key),
                "tags": list(f.tags),
            }
            if f.stroke_width is not None:
                row["stroke_width"] = f.stroke_width
            if f.stroke_color is not None:
                row["stroke_color"] = f.stroke_color
            if f.stroke_dash is not None:
                row["stroke_dash"] = f.stroke_dash
            if f.layer_z is not None:
                row["layer_z"] = f.layer_z
            ef_out.append(row)
        board_payload["edge_features"] = ef_out
    if state.board.linear_features:
        lf_out: list[dict[str, Any]] = []
        for f in state.board.linear_features:
            row_l: dict[str, Any] = {
                "feature_id": f.feature_id,
                "path": [_hex_wire(h) for h in f.path_hexes],
                "tags": list(f.tags),
            }
            if f.stroke_width is not None:
                row_l["stroke_width"] = f.stroke_width
            if f.stroke_color is not None:
                row_l["stroke_color"] = f.stroke_color
            if f.stroke_dash is not None:
                row_l["stroke_dash"] = f.stroke_dash
            if f.layer_z is not None:
                row_l["layer_z"] = f.layer_z
            lf_out.append(row_l)
        board_payload["linear_features"] = lf_out

    board_payload["linear_movement"] = {
        t: c for t, c in state.board.linear_movement_by_tag
    }
    if state.board.edge_movement_extra_by_tag:
        board_payload["edge_movement_extra"] = {
            t: c for t, c in state.board.edge_movement_extra_by_tag
        }
    if state.board.edge_line_of_sight_by_tag:
        board_payload["edge_line_of_sight"] = {
            t: v for t, v in state.board.edge_line_of_sight_by_tag
        }

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
    if state.session_state:
        out["session_state"] = dict(state.session_state)
    if state.engine_state:
        out["engine_state"] = dict(state.engine_state)
    if state.session_state_key:
        out["session_state_key"] = state.session_state_key
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

    def _parse_hex(d: dict[str, Any]) -> Hex:
        return Hex(i=int(d["i"]), j=int(d["j"]), k=int(d["k"]))

    def _parse_edge_key(d: dict[str, Any]) -> EdgeKey:
        return EdgeKey(
            _parse_hex(d["hex_low"]),
            _parse_hex(d["hex_high"]),
        )

    edge_features: tuple[BoardEdgeFeature, ...] = ()
    raw_ef = state_dict.get("board", {}).get("edge_features")
    if isinstance(raw_ef, list) and raw_ef:
        ef_list: list[BoardEdgeFeature] = []
        for i, row in enumerate(raw_ef):
            if not isinstance(row, dict):
                raise ValueError(f"board.edge_features[{i}] must be an object")
            raw_tags = row.get("tags", [])
            tags = tuple(str(x).strip() for x in raw_tags) if raw_tags else ()
            ek = _parse_edge_key(row["edge_key"])
            sw = row.get("stroke_width")
            raw_sc = row.get("stroke_color")
            stroke_color = (
                None if raw_sc is None else (s if (s := str(raw_sc).strip()) else None)
            )
            sd = row.get("stroke_dash")
            lz = row.get("layer_z")
            ef_list.append(
                BoardEdgeFeature(
                    feature_id=str(row["feature_id"]),
                    edge_key=ek,
                    tags=tags,
                    stroke_width=None if sw is None else float(sw),
                    stroke_color=stroke_color,
                    stroke_dash=None if sd is None else str(sd),
                    layer_z=None if lz is None else int(lz),
                )
            )
        edge_features = tuple(ef_list)

    linear_features: tuple[BoardLinearFeature, ...] = ()
    raw_lf = state_dict.get("board", {}).get("linear_features")
    if isinstance(raw_lf, list) and raw_lf:
        lf_list: list[BoardLinearFeature] = []
        for i, row in enumerate(raw_lf):
            if not isinstance(row, dict):
                raise ValueError(f"board.linear_features[{i}] must be an object")
            path_raw = row["path"]
            if not isinstance(path_raw, list) or len(path_raw) < 2:
                raise ValueError(
                    f"board.linear_features[{i}].path must have at least two hexes"
                )
            path_hexes = tuple(_parse_hex(p) for p in path_raw)
            raw_tags = row.get("tags", [])
            tags = tuple(str(x).strip() for x in raw_tags) if raw_tags else ()
            sw = row.get("stroke_width")
            raw_sc = row.get("stroke_color")
            stroke_color = (
                None if raw_sc is None else (s if (s := str(raw_sc).strip()) else None)
            )
            sd = row.get("stroke_dash")
            lz = row.get("layer_z")
            lf_list.append(
                BoardLinearFeature(
                    feature_id=str(row["feature_id"]),
                    path_hexes=path_hexes,
                    tags=tags,
                    stroke_width=None if sw is None else float(sw),
                    stroke_color=stroke_color,
                    stroke_dash=None if sd is None else str(sd),
                    layer_z=None if lz is None else int(lz),
                )
            )
        for lf in lf_list:
            validate_linear_hex_path(lf.path_hexes)
        linear_features = tuple(lf_list)

    b = state_dict.get("board", {})
    if not isinstance(b, dict):
        b = {}
    ls_merged: dict[str, float] = {}
    raw_ls = b.get("linear_movement")
    if isinstance(raw_ls, dict):
        for k, v in raw_ls.items():
            tag = str(k).strip()
            if not tag:
                raise ValueError("board.linear_movement: empty tag key is not allowed")
            if isinstance(v, str) and v.lower() == "inf":
                ls_merged[tag] = float("inf")
            else:
                ls_merged[tag] = float(v)
    linear_movement_by_tag = tuple(sorted(ls_merged.items(), key=lambda kv: kv[0]))

    em_merged: dict[str, float] = {}
    raw_em = b.get("edge_movement_extra")
    if isinstance(raw_em, dict):
        for k, v in raw_em.items():
            tag = str(k).strip()
            if not tag:
                raise ValueError(
                    "board.edge_movement_extra: empty tag key is not allowed"
                )
            if isinstance(v, str) and v.lower() == "inf":
                em_merged[tag] = float("inf")
            else:
                em_merged[tag] = float(v)
    edge_movement_extra_by_tag = tuple(sorted(em_merged.items(), key=lambda kv: kv[0]))

    elos_merged: dict[str, bool] = {}
    raw_elos = b.get("edge_line_of_sight")
    if isinstance(raw_elos, dict):
        for k, v in raw_elos.items():
            tag = str(k).strip()
            if not tag:
                raise ValueError(
                    "board.edge_line_of_sight: empty tag key is not allowed"
                )
            elos_merged[tag] = bool(v)
    edge_line_of_sight_by_tag = tuple(sorted(elos_merged.items(), key=lambda kv: kv[0]))

    board = BoardState(
        units=units,
        locations=locations,
        unset_defaults=unset_defaults,
        edge_features=edge_features,
        linear_features=linear_features,
        linear_movement_by_tag=linear_movement_by_tag,
        edge_movement_extra_by_tag=edge_movement_extra_by_tag,
        edge_line_of_sight_by_tag=edge_line_of_sight_by_tag,
    )

    turn_data = state_dict.get("turn")
    if not isinstance(turn_data, dict):
        raise ValueError("game_state.turn must be an object")
    for key in ("current_faction", "current_phase", "phase_actions_remaining"):
        if key not in turn_data:
            raise ValueError(f"game_state.turn.{key} is required")
    fac_s = wire_str(turn_data["current_faction"]).strip()
    phase_s = wire_str(turn_data["current_phase"]).strip()
    if not fac_s or not phase_s:
        raise ValueError(
            "game_state.turn.current_faction and current_phase must be non-empty"
        )
    turn = TurnState(
        turn_number=int(turn_data.get("turn_number", 1)),
        current_faction=fac_s,
        current_phase=phase_s,
        phase_actions_remaining=int(turn_data["phase_actions_remaining"]),
        schedule_index=int(turn_data.get("schedule_index", 0)),
        global_tick=int(turn_data.get("global_tick", 0)),
    )

    raw_ts = state_dict.get("session_state")
    raw_es = state_dict.get("engine_state")
    raw_key = state_dict.get("session_state_key")
    session_state: dict[str, Any] = dict(raw_ts) if isinstance(raw_ts, dict) else {}
    engine_state: dict[str, Any] = dict(raw_es) if isinstance(raw_es, dict) else {}
    session_state_key: str | None = None
    if isinstance(raw_key, str) and raw_key.strip():
        session_state_key = raw_key.strip()

    raw_rng = state_dict.get("rng_log", [])
    if isinstance(raw_rng, dict):
        raw_iter_rng = raw_rng.values()
    else:
        raw_iter_rng = raw_rng
    rng_log: tuple[dict[str, Any], ...] = tuple(
        dict(x) for x in raw_iter_rng if isinstance(x, dict)
    )

    return GameState(
        board=board,
        turn=turn,
        session_state=session_state,
        engine_state=engine_state,
        session_state_key=session_state_key,
        rng_log=rng_log,
    )
