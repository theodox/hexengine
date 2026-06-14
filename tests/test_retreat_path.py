"""Retreat path preview and stepwise commit."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GAMES = str(REPO_ROOT / "games")
if GAMES not in sys.path:
    sys.path.insert(0, GAMES)

from hexengine.gamedef.interactions import InteractionKind
from hexengine.hexes.types import Hex
from hexengine.retreat_path import (
    can_complete_retreat_in_steps,
    legal_next_retreat_path_hexes,
)
from hexengine.server.game_server import GameServer
from hexengine.server.map_selection import compute_map_selection_preview


def _hexdemo_server() -> GameServer:
    from hexdemo.game_config import (
        default_match_config,
        game_definition_from_config,
    )
    from hexengine.scenarios import load_scenario
    from hexengine.scenarios.loader import scenario_to_initial_state

    scenario_path = (
        REPO_ROOT / "games" / "hexdemo" / "scenarios" / "default" / "scenario.toml"
    )
    scenario_data = load_scenario(scenario_path)
    gd = game_definition_from_config(default_match_config())
    first = {"faction": "union", "phase": "Combat", "max_actions": 4}
    st = scenario_to_initial_state(
        scenario_data,
        initial_faction=first["faction"],
        initial_phase=first["phase"],
        phase_actions_remaining=int(first["max_actions"]),
        schedule_index=0,
        game_definition=gd,
    )
    return GameServer(
        initial_state=st,
        game_definition=gd,
        pack_id="hexdemo",
        pack_root=REPO_ROOT / "games" / "hexdemo",
    )


def test_registry_includes_retreat_path_kind() -> None:
    from hexengine.hooks.map_selection_registry import map_selection_kinds_in_registry

    kinds = map_selection_kinds_in_registry()
    assert InteractionKind.RETREAT_PATH in kinds


def test_hexdemo_binds_retreat_path_preview() -> None:
    from hexdemo.registry import build_game_definition

    th = build_game_definition().hooks
    assert th.modification.retreat_path_preview is not None


def test_can_complete_retreat_in_steps() -> None:
    assert can_complete_retreat_in_steps(1, 3, 2) is True
    assert can_complete_retreat_in_steps(1, 3, 1) is False
    assert can_complete_retreat_in_steps(2, 3, 1) is True
    assert can_complete_retreat_in_steps(3, 3, 0) is True


def test_legal_next_blocks_same_ring_dead_end() -> None:
    """Sideways steps on the same distance ring must not use up the step budget."""
    from hexengine.state.game_state import (
        BoardState,
        GameState,
        LocationState,
        TurnState,
        UnitState,
    )

    s = Hex(0, 0, 0)
    a = Hex(1, -1, 0)
    b = Hex(0, -1, 1)

    def loc(h):
        return LocationState(position=h, terrain_type="plain", movement_cost=1.0)

    board = BoardState(
        locations={s: loc(s), a: loc(a), b: loc(b)},
        units={"u": UnitState("u", "inf", "union", s, active=True)},
    )
    st = GameState(board=board, turn=TurnState("union", "Combat", 1, 1, 0, 0))
    first = legal_next_retreat_path_hexes(
        state=st,
        unit_id="u",
        path=(s,),
        obligation=3,
        player_faction="union",
        blocked_hexes=None,
        max_active_units_per_hex=None,
        step_cost=None,
    )
    assert a in first
    sideways = legal_next_retreat_path_hexes(
        state=st,
        unit_id="u",
        path=(s, a),
        obligation=3,
        player_faction="union",
        blocked_hexes=None,
        max_active_units_per_hex=None,
        step_cost=None,
    )
    assert b not in sideways


def test_legal_next_allows_outward_after_sideways_detour() -> None:
    from hexengine.state.game_state import (
        BoardState,
        GameState,
        LocationState,
        TurnState,
        UnitState,
    )

    s = Hex(0, 0, 0)
    a = Hex(1, -1, 0)
    c = Hex(2, -2, 0)

    def loc(h):
        return LocationState(position=h, terrain_type="plain", movement_cost=1.0)

    board = BoardState(
        locations={s: loc(s), a: loc(a), c: loc(c)},
        units={"u": UnitState("u", "inf", "union", s, active=True)},
    )
    st = GameState(board=board, turn=TurnState("union", "Combat", 1, 1, 0, 0))
    after_sideways = legal_next_retreat_path_hexes(
        state=st,
        unit_id="u",
        path=(s, a),
        obligation=3,
        player_faction="union",
        blocked_hexes=None,
        max_active_units_per_hex=None,
        step_cost=None,
    )
    assert c in after_sideways


def test_legal_next_includes_distant_end_hexes() -> None:
    from hexengine.state.game_state import (
        BoardState,
        GameState,
        LocationState,
        TurnState,
        UnitState,
    )

    a = Hex(0, 0, 0)
    b = Hex(1, -1, 0)
    c = Hex(2, -2, 0)

    def loc(h):
        return LocationState(position=h, terrain_type="plain", movement_cost=1.0)

    board = BoardState(
        locations={a: loc(a), b: loc(b), c: loc(c)},
        units={"u": UnitState("u", "inf", "union", a, active=True)},
    )
    st = GameState(board=board, turn=TurnState("union", "Combat", 1, 1, 0, 0))
    legal = legal_next_retreat_path_hexes(
        state=st,
        unit_id="u",
        path=(a,),
        obligation=2,
        player_faction="union",
        blocked_hexes=None,
        max_active_units_per_hex=None,
        step_cost=None,
    )
    assert c in legal
    assert b in legal


def test_retreat_path_preview_via_compute_map_selection() -> None:
    server = _hexdemo_server()
    st = server.action_manager.current_state
    uid = next(iter(st.board.units.keys()))
    u = st.board.units[uid]
    start = u.position
    raw = compute_map_selection_preview(
        state=st,
        player_faction=str(u.faction),
        kind=InteractionKind.RETREAT_PATH,
        draft={"unit_id": uid, "path": [{"i": start.i, "j": start.j, "k": start.k}]},
        shell_ui=dict(server.game_data.shell_ui or {}),
        board_hexes=server._iter_board_hexes(st),
        hooks=server.hooks,
    )
    assert raw.get("kind") == InteractionKind.RETREAT_PATH
    assert "panel_actions" in raw
    assert isinstance(raw.get("legal_next_hexes"), list)


def test_hexes_from_wire_rows_parsing() -> None:
    from hexengine.game.arcs.client_retreat_path import ClientRetreatPathMixin

    rows = [{"i": 0, "j": 0, "k": 0}, {"i": 1, "j": -1, "k": 0}]
    out = ClientRetreatPathMixin._hexes_from_wire_rows(rows)
    assert len(out) == 2
    assert out[0] == Hex(0, 0, 0)
    assert out[1] == Hex(1, -1, 0)


def test_retreat_path_polyline_hexes_prefers_local_draft() -> None:
    from hexengine.game.arcs.client_retreat_path import ClientRetreatPathMixin

    class _G(ClientRetreatPathMixin):
        retreat_path_hexes = [Hex(0, 0, 0), Hex(1, -1, 0), Hex(2, -2, 0)]

    g = _G()
    payload = {
        "preview_path_hexes": [{"i": 0, "j": 0, "k": 0}, {"i": 1, "j": -1, "k": 0}]
    }
    path = g._retreat_path_polyline_hexes(payload)
    assert len(path) == 3
    assert path[-1] == Hex(2, -2, 0)


def test_sync_retreat_path_refreshes_preview_after_highlights_cleared() -> None:
    """State sync clears hex highlights; an active one-hex draft must re-request preview."""
    from hexengine.game.arcs.client_retreat_path import ClientRetreatPathMixin
    from hexengine.hexes.types import Hex
    from hexengine.state import BoardState, GameState, TurnState, UnitState

    h0 = Hex(0, 0, 0)
    st = GameState(
        board=BoardState(
            units={
                "u_def": UnitState(
                    unit_id="u_def",
                    unit_type="inf",
                    faction="confederate",
                    position=h0,
                    active=True,
                ),
            }
        ),
        turn=TurnState(
            current_faction="union",
            current_phase="Combat",
            phase_actions_remaining=1,
            schedule_index=0,
        ),
    )

    preview_calls: list[dict] = []

    class _Client:
        faction = "confederate"
        retreat_obligations = {"u_def": 1}
        suggested_focus_unit_id = "u_def"

    class _G(ClientRetreatPathMixin):
        client = _Client()
        ui_state = type("_UI", (), {"selected_unit_id": "u_def"})()

        def _client_has_retreat_path_selection(self) -> bool:
            return True

        def retreat_obligation_hexes_remaining(self, _state, unit_id: str):
            return 1 if unit_id == "u_def" else None

        def _interactive_game_state(self):
            return st

        def _sync_retreat_obligation_unit_highlights(self, _state) -> None:
            pass

        def _request_map_selection_preview(self, kind, draft) -> None:
            preview_calls.append({"kind": kind, "draft": dict(draft)})

        def cancel_retreat_path(self) -> None:
            raise AssertionError("should not cancel active obligation draft")

    g = _G()
    g.retreat_path_unit_id = "u_def"
    g.retreat_path_hexes = [h0]

    from hexengine.game.game import Game

    Game._sync_retreat_path_after_state_update(g, st)

    assert len(preview_calls) == 1
    assert preview_calls[0]["draft"]["unit_id"] == "u_def"


def test_map_selection_preview_wire_carries_retreat_hex_fields() -> None:
    from hexengine.server.protocol import MapSelectionPreviewWire

    legal = [{"i": 2, "j": -2, "k": 0}]
    through = [{"i": 1, "j": -1, "k": 0}]
    wire = MapSelectionPreviewWire(
        kind=InteractionKind.RETREAT_PATH,
        status_text="Pick destination",
        confirm_enabled=False,
        request_id="abc",
        legal_next_hexes=legal,
        through_hexes=through,
        preview_path_hexes=[{"i": 0, "j": 0, "k": 0}],
    )
    msg = wire.to_message()
    back = MapSelectionPreviewWire.from_message(msg)
    assert back.legal_next_hexes == legal
    assert back.through_hexes == through
    assert back.preview_path_hexes == [{"i": 0, "j": 0, "k": 0}]


def test_retreat_path_confirm_move_unit_with_path_wire() -> None:
    """Confirming a retreat path sends ``path`` on MoveUnit; server must pass GameState to hooks."""
    import asyncio

    from hexengine.hexes.math import neighbors
    from hexengine.server.protocol import ActionRequest, JoinGameRequest, PlayerInfo
    from hexengine.state.game_state import BoardState, TurnState, UnitState

    h0 = Hex(0, 0, 0)
    h1 = next(n for n in neighbors(h0))
    h2 = next(n for n in neighbors(h1) if n != h0)
    board = BoardState(
        units={
            "u_def": UnitState(
                unit_id="u_def",
                unit_type="inf",
                faction="confederate",
                position=h1,
                health=10,
                active=True,
            ),
            "u_att": UnitState(
                unit_id="u_att",
                unit_type="inf",
                faction="union",
                position=h0,
                health=10,
                active=True,
            ),
        }
    )
    turn = TurnState("union", "Combat", 2, 1, 0, 0)
    ext = {
        "hexdemo": {
            "disrupt_instead_offered": True,
            "retreat_obligations": {"u_def": 2},
        }
    }
    from hexengine.state import GameState

    st = GameState(
        board=board,
        turn=turn,
        session_state=ext.get("hexdemo", {}),
        session_state_key="hexdemo",
        rng_log=(),
    )
    server = _hexdemo_server()
    server.action_manager.replace_state(st)
    server.players["p_c"] = PlayerInfo(
        player_id="p_c", player_name="C", faction="confederate", connected=True
    )
    server.faction_to_player["confederate"] = "p_c"
    errors: list[str] = []

    async def run() -> None:
        def capture(_pid: str, m) -> None:
            if m.type == "error":
                errors.append(str(m.payload.get("error", "")))

        server.add_message_handler(capture)
        await server.handle_message(
            "p_c", JoinGameRequest(player_name="C", faction="confederate").to_message()
        )
        req = ActionRequest(
            action_type="MoveUnit",
            params={
                "unit_id": "u_def",
                "from_hex": {"i": h1.i, "j": h1.j, "k": h1.k},
                "to_hex": {"i": h2.i, "j": h2.j, "k": h2.k},
                "path": [
                    {"i": h1.i, "j": h1.j, "k": h1.k},
                    {"i": h0.i, "j": h0.j, "k": h0.k},
                    {"i": h2.i, "j": h2.j, "k": h2.k},
                ],
            },
            player_id="p_c",
        )
        await server.handle_message("p_c", req.to_message())

    asyncio.run(run())
    assert not any("has no attribute 'board'" in e for e in errors), errors
    assert not errors or all("Illegal" not in e for e in errors), errors
