"""
Map `hexengine.scenarios.schema.ScenarioData` onto `hexengine.state.GameState`.

When `hexengine.state.game_state.BoardState` / unit or location state types change,
update `scenario_to_initial_state` here.
"""

from __future__ import annotations

from ..gamedef.protocol import GameDefinition
from ..gamedef.unit_attributes import merge_spawn_attributes
from ..hexes.centerline import (
    linear_feature_path_around_hexes,
    validate_linear_hex_path,
)
from ..hexes.edges import (
    edge_between,
    edge_keys_along_hex_chain,
    shortest_edge_key_path_for_hex_spine,
)
from ..hexes.math import distance, neighbor_hex
from ..hexes.shapes import path as hex_grid_path
from ..hexes.types import Hex, HexColRow
from ..hexes.vertices import shortest_edge_key_path_hex_corridor_vertex_space
from ..state import GameState
from ..state.game_state import (
    BoardEdgeFeature,
    BoardLinearFeature,
    BoardState,
    LocationState,
    UnitState,
    UnsetTerrainDefaults,
)
from .schema import (
    EdgeEndpointSpec,
    EdgeFeatureSpec,
    LinearFeatureSpec,
    ScenarioData,
    TerrainTypeRow,
)

# Vertex-corridor search builds an incident-edge graph over all path hexes; skip it on
# long corridors so scenario load stays responsive (stitched spine is still used).
_MAX_EDGE_VERTEX_PATH_HEXES = 36


def _hex(pos: tuple[int, int]) -> Hex:
    """Scenario `Position` is odd-q `(col, row)`."""
    return Hex.from_hex_col_row(HexColRow(col=pos[0], row=pos[1]))


def _ordered_hex_pair(
    endpoint: EdgeEndpointSpec, ctx: str
) -> tuple[tuple[int, int], tuple[int, int]]:
    if endpoint.between is not None:
        (c0, r0), (c1, r1) = endpoint.between
        a = Hex.from_hex_col_row(HexColRow(col=c0, row=r0))
        b = Hex.from_hex_col_row(HexColRow(col=c1, row=r1))
        if edge_between(a, b) is None:
            raise ValueError(f"{ctx}: edge endpoints are not cube-adjacent hexes")
        return ((c0, r0), (c1, r1))
    if endpoint.position is None or endpoint.direction is None:
        raise ValueError(f"{ctx}: need between or position + direction")
    a = Hex.from_hex_col_row(
        HexColRow(col=endpoint.position[0], row=endpoint.position[1])
    )
    b = neighbor_hex(a, endpoint.direction)
    cr = HexColRow.offset_from_axial(b.i, b.j)
    return (endpoint.position, (cr.col, cr.row))


def _dedupe_consecutive_hexes(cells: list[Hex]) -> list[Hex]:
    out: list[Hex] = []
    for h in cells:
        if not out or out[-1] != h:
            out.append(h)
    return out


def _extend_cells_for_end_edge(
    cells: list[Hex], end_spec: EdgeEndpointSpec, ctx: str
) -> list[Hex]:
    e0, e1 = _ordered_hex_pair(end_spec, ctx)
    ha = Hex.from_hex_col_row(HexColRow(col=e0[0], row=e0[1]))
    hb = Hex.from_hex_col_row(HexColRow(col=e1[0], row=e1[1]))
    ek_want = edge_between(ha, hb)
    if ek_want is None:
        raise ValueError(f"{ctx}: end_edge endpoints are not adjacent")
    keys_try = edge_keys_along_hex_chain(tuple(cells))
    if keys_try[-1] == ek_want:
        return cells
    last = cells[-1]
    if last == ha and distance(last, hb) == 1:
        extended = cells + [hb]
        if edge_keys_along_hex_chain(tuple(extended))[-1] == ek_want:
            return extended
    raise ValueError(
        f"{ctx}: path does not match end_edge (last key {keys_try[-1]!r}, want {ek_want!r})"
    )


def _edge_features_from_spec(spec: EdgeFeatureSpec) -> tuple[BoardEdgeFeature, ...]:
    ctx = f"edge_features {spec.feature_id!r}"
    p0, p1 = _ordered_hex_pair(spec.start_edge, f"{ctx}.start_edge")
    steps: list[HexColRow] = [
        HexColRow(col=p0[0], row=p0[1]),
        HexColRow(col=p1[0], row=p1[1]),
    ]
    steps.extend(HexColRow(col=c, row=r) for c, r in spec.waypoints)
    cells = _dedupe_consecutive_hexes(list(hex_grid_path(tuple(steps))))
    if spec.end_edge is not None:
        cells = _extend_cells_for_end_edge(cells, spec.end_edge, f"{ctx}.end_edge")
    if len(cells) < 2:
        raise ValueError(f"{ctx}: need at least two hex centers along the path")
    cells_tuple = tuple(cells)
    spine = edge_keys_along_hex_chain(
        cells_tuple,
        start_side=spec.start_side,
        end_side=spec.end_side,
    )
    if not spine or len(spine) != len(cells_tuple) - 1:
        raise ValueError(
            f"{ctx}: internal error building spine "
            f"(len(spine)={len(spine)}, len(cells)={len(cells_tuple)})"
        )
    p0s, p1s = _ordered_hex_pair(spec.start_edge, f"{ctx}.start_edge")
    h_sa = Hex.from_hex_col_row(HexColRow(col=p0s[0], row=p0s[1]))
    h_sb = Hex.from_hex_col_row(HexColRow(col=p1s[0], row=p1s[1]))
    start_ek = edge_between(h_sa, h_sb)
    if start_ek is None:
        raise ValueError(f"{ctx}.start_edge: endpoints must be adjacent hexes")
    if spec.end_edge is not None:
        e0, e1 = _ordered_hex_pair(spec.end_edge, f"{ctx}.end_edge")
        h_ea = Hex.from_hex_col_row(HexColRow(col=e0[0], row=e0[1]))
        h_eb = Hex.from_hex_col_row(HexColRow(col=e1[0], row=e1[1]))
        goal_ek = edge_between(h_ea, h_eb)
        if goal_ek is None:
            raise ValueError(f"{ctx}.end_edge: endpoints must be adjacent hexes")
    else:
        goal_ek = spine[-1]
    keys_stitch = None
    try:
        keys_stitch = shortest_edge_key_path_for_hex_spine(
            cells_tuple, None, start_ek, goal_ek, spine=spine
        )
    except Exception:
        keys_stitch = None

    if keys_stitch is not None and (
        keys_stitch[0] != start_ek or keys_stitch[-1] != goal_ek
    ):
        raise ValueError(
            f"{ctx}: internal: stitched walk endpoints "
            f"{keys_stitch[0]!r}..{keys_stitch[-1]!r} != {start_ek!r}..{goal_ek!r}"
        )

    keys_vertex = None
    want_vertex = keys_stitch is None or (
        keys_stitch is not None and len(keys_stitch) > len(spine)
    )
    need_vertex = want_vertex and len(cells_tuple) <= _MAX_EDGE_VERTEX_PATH_HEXES
    if need_vertex:
        try:
            keys_vertex = shortest_edge_key_path_hex_corridor_vertex_space(
                cells_tuple, None, start_ek, goal_ek
            )
        except Exception:
            keys_vertex = None

    if keys_vertex is not None and (
        keys_vertex[0] != start_ek or keys_vertex[-1] != goal_ek
    ):
        raise ValueError(
            f"{ctx}: internal: vertex walk endpoints "
            f"{keys_vertex[0]!r}..{keys_vertex[-1]!r} != {start_ek!r}..{goal_ek!r}"
        )

    if keys_vertex is not None and keys_stitch is not None:
        keys_opt = keys_vertex if len(keys_vertex) <= len(keys_stitch) else keys_stitch
    elif keys_stitch is not None:
        keys_opt = keys_stitch
    else:
        keys_opt = keys_vertex

    if keys_opt is None:
        raise ValueError(
            f"{ctx}: no edge walk from start_edge to goal edge along the path hexes "
            f"(stitch and vertex both missing). "
            f"spine_len={len(spine)}, "
            f"stitch_len={len(keys_stitch) if keys_stitch else None}, "
            f"vertex_len={len(keys_vertex) if keys_vertex else None}, "
            f"want_vertex={want_vertex!r}, need_vertex={need_vertex!r}, "
            f"path_hexes={len(cells_tuple)}, max_vertex_hexes={_MAX_EDGE_VERTEX_PATH_HEXES}, "
            f"start_ek={start_ek!r}, goal_ek={goal_ek!r}"
        )
    if keys_opt[0] != start_ek or keys_opt[-1] != goal_ek:
        raise ValueError(
            f"{ctx}: internal: chosen walk endpoints "
            f"{keys_opt[0]!r}..{keys_opt[-1]!r} != {start_ek!r}..{goal_ek!r}"
        )
    keys = keys_opt
    n = len(keys)
    return tuple(
        BoardEdgeFeature(
            feature_id=spec.feature_id if n == 1 else f"{spec.feature_id}~{i}",
            edge_key=k,
            tags=spec.tags,
            stroke_width=spec.stroke_width,
            stroke_color=spec.stroke_color,
            stroke_dash=spec.stroke_dash,
            layer_z=spec.layer_z,
        )
        for i, k in enumerate(keys)
    )


def _linear_feature_from_spec(spec: LinearFeatureSpec) -> BoardLinearFeature:
    modes = sum(
        1 for x in (spec.path, spec.perimeter_of, spec.waypoints) if x is not None
    )
    if modes != 1:
        raise ValueError(
            f"linear_features {spec.feature_id!r}: internal error, expected one of path / perimeter_of / waypoints"
        )
    if spec.perimeter_of is not None:
        hexes = linear_feature_path_around_hexes(
            tuple(HexColRow(col=c, row=r) for c, r in spec.perimeter_of)
        ).hexes
    elif spec.path is not None:
        hexes = tuple(_hex((c, r)) for c, r in spec.path)
        validate_linear_hex_path(hexes)
    else:
        assert spec.waypoints is not None
        wps = tuple(HexColRow(col=c, row=r) for c, r in spec.waypoints)
        merged: list[Hex] = []
        for h in hex_grid_path(wps):
            if not merged or merged[-1] != h:
                merged.append(h)
        hexes = tuple(merged)
        validate_linear_hex_path(hexes)
    return BoardLinearFeature(
        feature_id=spec.feature_id,
        path_hexes=hexes,
        tags=spec.tags,
        stroke_width=spec.stroke_width,
        stroke_color=spec.stroke_color,
        stroke_dash=spec.stroke_dash,
        layer_z=spec.layer_z,
    )


def _unset_defaults_from_terrain_types(
    types: tuple[TerrainTypeRow, ...],
) -> UnsetTerrainDefaults:
    default = next(t for t in types if t.is_default)
    return UnsetTerrainDefaults(
        terrain_type=default.terrain_type,
        movement_cost=default.movement_cost,
        hex_color=default.hex_color,
        assault_modifier=default.assault_modifier,
        ranged_modifier=default.ranged_modifier,
        block_los=default.block_los,
    )


def scenario_to_initial_state(
    data: ScenarioData,
    *,
    initial_faction: str,
    initial_phase: str = "Movement",
    phase_actions_remaining: int = 2,
    schedule_index: int = 0,
    game_definition: GameDefinition | None = None,
) -> GameState:
    """
    Build an initial GameState from scenario data (server path).

    Does not use ActionManager — constructs state directly. When BoardState
    or UnitState/LocationState change, update only this function.

    `initial_faction` / `initial_phase` / `phase_actions_remaining` / `schedule_index`
    should match the first rota slot (see `hexengine.gameroot.initial_turn_slot_for_game_definition`).

    When game_definition is set, initial UnitState.attributes are filled via
    merge_spawn_attributes (type defaults + each row's UnitRow.attributes).
    With no definition, scenario attributes tables are copied as-is.
    """
    from ..state.game_state import TurnState

    board = BoardState(
        unset_defaults=_unset_defaults_from_terrain_types(data.terrain_types),
        edge_features=tuple(
            f for s in data.edge_features for f in _edge_features_from_spec(s)
        ),
        linear_features=tuple(
            _linear_feature_from_spec(s) for s in data.linear_features
        ),
        linear_movement_by_tag=data.linear_movement_by_tag,
        edge_movement_extra_by_tag=data.edge_movement_extra_by_tag,
        edge_line_of_sight_by_tag=data.edge_line_of_sight_by_tag,
    )
    turn = TurnState(
        current_faction=initial_faction,
        current_phase=initial_phase,
        phase_actions_remaining=phase_actions_remaining,
        turn_number=1,
        schedule_index=schedule_index,
        global_tick=0,
    )

    for loc in data.locations:
        board = board.with_location(
            LocationState(
                position=_hex(loc.position),
                terrain_type=loc.terrain_type,
                movement_cost=loc.movement_cost,
                hex_color=loc.hex_color,
                assault_modifier=loc.assault_modifier,
                ranged_modifier=loc.ranged_modifier,
                block_los=loc.block_los,
            )
        )

    for u in data.units:
        pos = _hex(u.position)
        instance_attrs = dict(u.attributes)
        merged_attrs = (
            merge_spawn_attributes(
                game_definition, u.unit_type, instance_attrs, state=None
            )
            if game_definition is not None
            else instance_attrs
        )
        si = board.next_stack_index_at_hex(pos)
        board = board.with_unit(
            UnitState(
                unit_id=u.unit_id,
                unit_type=u.unit_type,
                faction=u.faction,
                position=pos,
                health=u.health,
                active=u.active,
                stack_index=si,
                graphics=u.graphics,
                attributes=dict(merged_attrs),
            )
        )

    return GameState(board=board, turn=turn, rng_log=())
