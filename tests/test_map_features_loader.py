from __future__ import annotations

import pytest
from games.hexdemo.movement import rules as movement_rules

from hexengine.hexes.edges import (
    edge_between,
    edge_keys_along_hex_chain,
    shortest_edge_key_path_for_hex_spine,
)
from hexengine.hexes.types import Hex, HexColRow
from hexengine.hexes.vertices import shortest_edge_key_path_hex_corridor_vertex_space
from hexengine.scenarios.load.parse import load_scenario
from hexengine.scenarios.loader import scenario_to_initial_state
from hexengine.state import (
    board_edge_features_along_hex_line,
    compute_reachable_hexes,
    edge_keys_along_hex_line,
    edge_movement_extra_for_neighbor_step,
    game_state_from_wire_dict,
    game_state_to_wire_dict,
    linear_features_on_neighbor_step,
    min_linear_movement_cost_for_tags,
)
from hexengine.state.game_state import (
    BoardEdgeFeature,
    BoardLinearFeature,
    BoardState,
    GameState,
    TurnState,
    UnsetTerrainDefaults,
)


def test_edge_keys_along_hex_line_matches_steps() -> None:
    a = Hex(0, 0, 0)
    b = Hex(2, -1, -1)
    keys = edge_keys_along_hex_line(a, b)
    assert len(keys) == 2
    assert keys[0] == edge_between(a, Hex(1, 0, -1))
    assert keys[1] == edge_between(Hex(1, 0, -1), b)


def test_scenario_edge_and_linear_round_trip_wire() -> None:
    h0 = Hex.from_hex_col_row(HexColRow(0, 0))
    h1 = Hex.from_hex_col_row(HexColRow(1, 0))
    ek = edge_between(h0, h1)
    assert ek is not None
    st = GameState(
        board=BoardState(
            edge_features=(
                BoardEdgeFeature(
                    feature_id="e1",
                    edge_key=ek,
                    tags=("river",),
                    stroke_width=3.0,
                    stroke_color="#4a90d9",
                ),
            ),
            linear_features=(
                BoardLinearFeature(
                    feature_id="r1",
                    path_hexes=(h0, h1, Hex.from_hex_col_row(HexColRow(2, 0))),
                    tags=("road",),
                    stroke_width=2.0,
                    stroke_color="#a67c52",
                ),
            ),
        ),
        turn=TurnState(
            current_faction="A",
            current_phase="Move",
            phase_actions_remaining=1,
        ),
    )
    w = game_state_to_wire_dict(st)
    st2 = game_state_from_wire_dict(w)
    assert len(st2.board.edge_features) == 1
    assert st2.board.edge_features[0].tags == ("river",)
    assert st2.board.edge_features[0].stroke_width == 3.0
    assert st2.board.edge_features[0].stroke_color == "#4a90d9"
    assert len(st2.board.linear_features) == 1
    assert len(st2.board.linear_features[0].path_hexes) == 3
    assert st2.board.linear_features[0].stroke_width == 2.0
    assert st2.board.linear_features[0].stroke_color == "#a67c52"


def test_board_queries() -> None:
    h0 = Hex(0, 0, 0)
    h1 = Hex(1, 0, -1)
    ek = edge_between(h0, h1)
    assert ek is not None
    board = BoardState(
        edge_features=(BoardEdgeFeature(feature_id="x", edge_key=ek, tags=("wall",)),),
        linear_features=(
            BoardLinearFeature(feature_id="p", path_hexes=(h0, h1), tags=("road",)),
        ),
    )
    feats = board_edge_features_along_hex_line(board, h0, Hex(3, 0, -3))
    assert any(f.feature_id == "x" for f in feats)
    step = linear_features_on_neighbor_step(board, h0, h1)
    assert len(step) == 1 and step[0].feature_id == "p"


def test_parse_edge_feature_requires_start_edge(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[edge_features]]",
                "waypoints = [ [0, 0], [1, 0] ]",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="requires start_edge"):
        load_scenario(p)


def test_parse_edge_feature_rejects_legacy_between(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[edge_features]]",
                "between = [ [0, 0], [1, 0] ]",
                "waypoints = [ [0, 0], [1, 0] ]",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="inside start_edge or end_edge"):
        load_scenario(p)


def test_parse_edge_feature_end_edge_extends_last_hex(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[edge_features]]",
                "start_edge = { between = [ [0, 0], [1, 0] ] }",
                "waypoints = [ [2, 0] ]",
                "end_edge = { between = [ [2, 0], [3, 0] ] }",
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.edge_features[0].end_edge is not None
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    h = tuple(
        Hex.from_hex_col_row(HexColRow(c, r))
        for c, r in ((0, 0), (1, 0), (2, 0), (3, 0))
    )
    spine = edge_keys_along_hex_chain(h)
    start_ek = edge_between(h[0], h[1])
    goal_ek = edge_between(h[2], h[3])
    keys_stitch = shortest_edge_key_path_for_hex_spine(
        h, None, start_ek, goal_ek, spine=spine
    )
    keys_vertex = shortest_edge_key_path_hex_corridor_vertex_space(
        h, None, start_ek, goal_ek
    )
    assert keys_stitch is not None and keys_vertex is not None
    # Matches loader: shorter of stitched spine vs vertex corridor when both exist.
    exp = keys_vertex if len(keys_vertex) <= len(keys_stitch) else keys_stitch
    assert len(gs.board.edge_features) == len(exp)
    assert tuple(f.edge_key for f in gs.board.edge_features) == exp


def test_parse_edge_feature_multi_cell_waypoints(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[edge_features]]",
                "start_edge = { between = [ [0, 0], [1, 0] ] }",
                "waypoints = [ [2, 0] ]",
                'tags = ["river"]',
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.edge_features[0].waypoints == ((2, 0),)
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    h = tuple(
        Hex.from_hex_col_row(HexColRow(c, r)) for c, r in ((0, 0), (1, 0), (2, 0))
    )
    spine = edge_keys_along_hex_chain(h)
    start_ek = edge_between(h[0], h[1])
    exp = shortest_edge_key_path_hex_corridor_vertex_space(h, None, start_ek, spine[-1])
    assert exp is not None
    assert len(gs.board.edge_features) == len(exp)
    assert gs.board.edge_features[0].feature_id == "edge-0~0"
    assert gs.board.edge_features[-1].feature_id == f"edge-0~{len(exp) - 1}"
    assert tuple(f.edge_key for f in gs.board.edge_features) == exp


def test_parse_minimal_scenario_map_features(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[edge_features]]",
                "start_edge = { between = [ [0, 0], [1, 0] ] }",
                'tags = ["river"]',
                "[[linear_features]]",
                "path = [ [0, 0], [1, 0], [2, 0] ]",
                'tags = ["road"]',
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert len(data.edge_features) == 1
    assert len(data.linear_features) == 1
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    assert len(gs.board.edge_features) == 1
    assert gs.board.edge_features[0].tags == ("river",)
    assert len(gs.board.linear_features[0].path_hexes) == 3
    assert data.linear_movement_by_tag == ()
    assert gs.board.linear_movement_by_tag == ()


def test_linear_movement_toml_and_wire(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "movement_cost = 1.0",
                "default = true",
                "[linear_movement]",
                "road = 0.5",
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.linear_movement_by_tag == (("road", 0.5),)
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    assert gs.board.linear_movement_by_tag == (("road", 0.5),)
    w = game_state_to_wire_dict(gs)
    assert w["board"]["linear_movement"] == {"road": 0.5}
    gs2 = game_state_from_wire_dict(w)
    assert gs2.board.linear_movement_by_tag == (("road", 0.5),)


def test_linear_movement_table_multiple_tags(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "movement_cost = 1.0",
                "default = true",
                "[linear_movement]",
                "road = 0.5",
                "rail = 0.25",
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.linear_movement_by_tag == (("rail", 0.25), ("road", 0.5))
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    assert gs.board.linear_movement_by_tag == (("rail", 0.25), ("road", 0.5))


def test_linear_movement_rows_form(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "movement_cost = 1.0",
                "default = true",
                "[[linear_movement]]",
                'tag = "road"',
                "movement_cost = 0.5",
                "[[linear_movement]]",
                'tag = "rail"',
                "movement_cost = 0.2",
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.linear_movement_by_tag == (("rail", 0.2), ("road", 0.5))


def test_edge_movement_extra_toml_and_wire(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "movement_cost = 1.0",
                "default = true",
                "[edge_movement_extra]",
                "river = 1.5",
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.edge_movement_extra_by_tag == (("river", 1.5),)
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    assert gs.board.edge_movement_extra_by_tag == (("river", 1.5),)
    w = game_state_to_wire_dict(gs)
    assert w["board"]["edge_movement_extra"] == {"river": 1.5}
    gs2 = game_state_from_wire_dict(w)
    assert gs2.board.edge_movement_extra_by_tag == (("river", 1.5),)


def test_edge_line_of_sight_toml_rows(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "movement_cost = 1.0",
                "default = true",
                "[[edge_line_of_sight]]",
                'tag = "river"',
                "blocks = true",
                "[[edge_line_of_sight]]",
                'tag = "wall"',
                "blocks = false",
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.edge_line_of_sight_by_tag == (("river", True), ("wall", False))


def test_edge_movement_extra_on_neighbor_step() -> None:
    h0 = Hex(0, 0, 0)
    h1 = Hex(1, 0, -1)
    ek = edge_between(h0, h1)
    assert ek is not None
    board = BoardState(
        edge_features=(
            BoardEdgeFeature(feature_id="riv", edge_key=ek, tags=("river", "scenic")),
        ),
        edge_movement_extra_by_tag=(("river", 1.0), ("scenic", 0.25)),
    )
    assert edge_movement_extra_for_neighbor_step(board, h0, h1) == pytest.approx(1.25)


def test_min_linear_movement_cost_for_tags() -> None:
    board = BoardState(
        linear_movement_by_tag=(("rail", 0.25), ("road", 0.5)),
    )
    assert min_linear_movement_cost_for_tags(board, ("road", "rail")) == 0.25
    assert min_linear_movement_cost_for_tags(board, ("trail",)) is None
    assert min_linear_movement_cost_for_tags(BoardState(), ("road",)) is None


def test_parse_map_feature_stroke_style_from_toml(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[edge_features]]",
                "start_edge = { between = [ [0, 0], [1, 0] ] }",
                "stroke_width = 4",
                'stroke_color = "#112233"',
                "[[linear_features]]",
                "path = [ [0, 0], [1, 0] ]",
                "stroke_width = 2.5",
                # shorthand for stroke_color
                'color = "#fedcba"',
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.edge_features[0].stroke_width == 4.0
    assert data.edge_features[0].stroke_color == "#112233"
    assert data.linear_features[0].stroke_width == 2.5
    assert data.linear_features[0].stroke_color == "#fedcba"
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    assert gs.board.edge_features[0].stroke_color == "#112233"
    assert gs.board.linear_features[0].stroke_color == "#fedcba"


def test_parse_linear_feature_perimeter_of_resolves_outline(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[linear_features]]",
                'feature_id = "ring"',
                # 2x2 parallelogram in odd-q (same block as centerline tests)
                "perimeter_of = [ [0, 0], [1, 0], [0, 1], [1, 1] ]",
                'tags = ["trail"]',
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.linear_features[0].path is None
    assert data.linear_features[0].perimeter_of is not None
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    path = gs.board.linear_features[0].path_hexes
    assert len(path) == 5
    assert path[0] == path[-1]


def test_parse_linear_feature_path_and_perimeter_mutually_exclusive(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[linear_features]]",
                "path = [ [0, 0], [1, 0] ]",
                "perimeter_of = [ [0, 0], [1, 0] ]",
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="exactly one of"):
        load_scenario(p)


def test_parse_linear_feature_waypoints_expands_hex_line(tmp_path) -> None:
    p = tmp_path / "scenario.toml"
    p.write_text(
        "\n".join(
            [
                'name = "t"',
                "schema_version = 1",
                "[[terrain_types]]",
                'terrain = "plain"',
                "default = true",
                "[[linear_features]]",
                "waypoints = [ [0, 0], [2, 0] ]",
                'tags = ["road"]',
            ]
        ),
        encoding="utf-8",
    )
    data = load_scenario(p)
    assert data.linear_features[0].waypoints == ((0, 0), (2, 0))
    gs = scenario_to_initial_state(
        data, initial_faction="Red", schedule_index=0, game_definition=None
    )
    assert len(gs.board.linear_features[0].path_hexes) == 3


def test_hexdemo_river_adds_step_cost() -> None:
    h0 = Hex(0, 0, 0)
    h1 = Hex(1, 0, -1)
    ek = edge_between(h0, h1)
    assert ek is not None
    ud = UnsetTerrainDefaults(
        terrain_type="plain",
        movement_cost=1.0,
        block_los=False,
    )
    board = BoardState(
        unset_defaults=ud,
        edge_features=(
            BoardEdgeFeature(feature_id="riv", edge_key=ek, tags=("river",)),
        ),
        edge_movement_extra_by_tag=(("river", 1.0),),
    )
    st = GameState(
        board=board,
        turn=TurnState(
            current_faction="Red",
            current_phase="Move",
            phase_actions_remaining=1,
        ),
    )

    def step_fn(s, f, t, b):
        return movement_rules.movement_step_cost_for_unit(s, "u", f, t, b)

    r1 = compute_reachable_hexes(st, h0, 1.0, step_cost=step_fn)
    assert h1 not in r1
    r2 = compute_reachable_hexes(st, h0, 2.0, step_cost=step_fn)
    assert h1 in r2


def test_hexdemo_road_linear_lowers_step_cost() -> None:
    h0 = Hex(0, 0, 0)
    h1 = Hex(1, 0, -1)
    h2 = Hex(2, 0, -2)
    ud = UnsetTerrainDefaults(
        terrain_type="plain",
        movement_cost=1.0,
        block_los=False,
    )
    board = BoardState(
        unset_defaults=ud,
        linear_features=(
            BoardLinearFeature(
                feature_id="r",
                path_hexes=(h0, h1, h2),
                tags=("road",),
            ),
        ),
        linear_movement_by_tag=(("road", 0.5),),
    )
    st = GameState(
        board=board,
        turn=TurnState(
            current_faction="Red",
            current_phase="Move",
            phase_actions_remaining=1,
        ),
    )

    def step_fn(s, f, t, b):
        return movement_rules.movement_step_cost_for_unit(s, "u", f, t, b)

    # Budget 0.75: two road steps (0.5+0.5) would exceed; one road step to h1 is ok.
    r = compute_reachable_hexes(st, h0, 0.75, step_cost=step_fn)
    assert h1 in r and h2 not in r
    r2 = compute_reachable_hexes(st, h0, 1.0, step_cost=step_fn)
    assert h2 in r2
