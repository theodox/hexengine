"""Zone of control: adjacent-enemy hexes and stop-on-entry reachability."""

from __future__ import annotations

from hexengine.hexes.math import neighbors
from hexengine.hexes.types import Hex
from hexengine.state.game_state import BoardState, GameState, TurnState, UnitState
from hexengine.state.game_state import LocationState
from hexengine.state.logic import (
    adjacent_enemy_zoc_hexes,
    adjacent_friendly_zoc_hexes,
    compute_valid_moves,
    compute_retreat_destination_hexes,
    is_valid_move,
    retreat_impassable_enemy_zoc_hexes,
)


def _move_phase_state(board: BoardState) -> GameState:
    return GameState(
        board=board,
        turn=TurnState(
            current_faction="union",
            current_phase="Move",
            phase_actions_remaining=2,
            turn_number=1,
            schedule_index=0,
            global_tick=0,
        ),
        extension={},
        rng_log=(),
    )


def test_adjacent_enemy_zoc_matches_neighbor_ring() -> None:
    enemy = Hex(0, 0, 0)
    board = BoardState(
        units={
            "c": UnitState("c", "inf", "confederate", enemy, active=True),
            "u": UnitState("u", "inf", "union", Hex(4, -2, -2), active=True),
        }
    )
    st = _move_phase_state(board)
    zoc = adjacent_enemy_zoc_hexes(st, "u")
    assert enemy not in zoc
    assert zoc == frozenset(neighbors(enemy))


def test_stop_on_zoc_entry_blocks_chain_past_first_zoc() -> None:
    """After stepping into a ZOC hex, the unit may not continue in the same move."""
    center = Hex(0, 0, 0)
    gate = Hex(1, -1, 0)
    # Neighbor of `gate` that is not itself in the ZOC ring from the surrounding enemies.
    past_gate = Hex(2, -2, 0)
    assert gate in neighbors(center)
    assert past_gate in neighbors(gate)

    # Funnel: union on center; confederates occupy every neighbor of center except `gate`,
    # so the first step must be onto `gate` (which lies in ZOC as adjacent to enemies).
    occupied = [h for h in neighbors(center) if h != gate]
    assert len(occupied) == 5
    units: dict[str, UnitState] = {
        "u": UnitState("u", "inf", "union", center, active=True),
    }
    for i, h in enumerate(occupied):
        units[f"c{i}"] = UnitState(f"c{i}", "inf", "confederate", h, active=True)

    board = BoardState(units=units)
    st = _move_phase_state(board)
    zoc = adjacent_enemy_zoc_hexes(st, "u")
    assert gate in zoc
    assert past_gate not in zoc

    budget = 4.0
    with_zoc = compute_valid_moves(st, "u", budget, zoc_hexes=zoc)
    no_zoc = compute_valid_moves(st, "u", budget, zoc_hexes=None)

    assert gate in with_zoc
    assert past_gate in no_zoc
    assert past_gate not in with_zoc


def test_start_in_zoc_can_leave_and_continue_on_clear_hexes() -> None:
    """Expansion is allowed from the start hex even when that hex is in ZOC."""
    enemy = Hex(0, 0, 0)
    start_on_zoc = Hex(1, -1, 0)
    assert start_on_zoc in frozenset(neighbors(enemy))
    clear_neighbor = Hex(2, -1, -1)
    assert clear_neighbor in neighbors(start_on_zoc)
    assert clear_neighbor not in frozenset(neighbors(enemy))

    board = BoardState(
        units={
            "c": UnitState("c", "inf", "confederate", enemy, active=True),
            "u": UnitState("u", "inf", "union", start_on_zoc, active=True),
        }
    )
    st = _move_phase_state(board)
    zoc = adjacent_enemy_zoc_hexes(st, "u")
    budget = 4.0

    valid = compute_valid_moves(st, "u", budget, zoc_hexes=zoc)
    assert clear_neighbor in valid
    assert is_valid_move(st, "u", clear_neighbor, budget, zoc_hexes=zoc)

    beyond = Hex(3, -1, -2)
    assert beyond in neighbors(clear_neighbor)
    assert beyond not in zoc
    assert is_valid_move(st, "u", beyond, budget, zoc_hexes=zoc)


def test_start_in_zoc_adjacent_zoc_neighbor_reachable_one_step() -> None:
    """From a ZOC start hex, another ZOC hex one step away is still a legal destination."""
    enemy = Hex(0, 0, 0)
    a = Hex(1, -1, 0)
    b = Hex(1, 0, -1)
    assert a in frozenset(neighbors(enemy))
    assert b in frozenset(neighbors(enemy))
    assert b in neighbors(a)

    board = BoardState(
        units={
            "c": UnitState("c", "inf", "confederate", enemy, active=True),
            "u": UnitState("u", "inf", "union", a, active=True),
        }
    )
    st = _move_phase_state(board)
    zoc = adjacent_enemy_zoc_hexes(st, "u")
    assert is_valid_move(st, "u", b, 1.0, zoc_hexes=zoc)


def test_retreat_impassable_helper_matches_enemy_minus_friendly() -> None:
    start = Hex(0, 0, 0)
    board = BoardState(
        units={
            "u": UnitState("u", "inf", "union", start, active=True),
            "e": UnitState("e", "inf", "confederate", Hex(1, 0, -1), active=True),
        }
    )
    st = _move_phase_state(board)
    manual = frozenset(
        h
        for h in adjacent_enemy_zoc_hexes(st, "u")
        if h not in adjacent_friendly_zoc_hexes(st, "u")
    )
    assert retreat_impassable_enemy_zoc_hexes(st, "u") == manual


def test_retreat_blocks_enemy_only_zoc_allows_overlap_with_friendly() -> None:
    """
    Retreat routing cannot pass through enemy ZOC unless that hex is also in friendly ZOC.
    """
    start = Hex(0, 0, 0)
    mid = Hex(1, -1, 0)
    dest = Hex(2, -2, 0)  # two steps away via `mid`
    enemy = Hex(1, 0, -1)  # projects enemy ZOC onto `mid`
    alt_mid = Hex(0, -1, 1)  # alternative path intermediate; make it impassable to force `mid`.

    board = BoardState(
        units={
            "u": UnitState("u", "inf", "union", start, active=True),
            "e": UnitState("e", "inf", "confederate", enemy, active=True),
        },
        locations={
            alt_mid: LocationState(
                position=alt_mid,
                terrain_type="impassable",
                movement_cost=float("inf"),
                block_los=True,
            )
        },
    )
    st = _move_phase_state(board)

    enemy_zoc = adjacent_enemy_zoc_hexes(st, "u")
    friendly_zoc = adjacent_friendly_zoc_hexes(st, "u")
    assert mid in enemy_zoc
    assert mid not in friendly_zoc
    blocked = frozenset(h for h in enemy_zoc if h not in friendly_zoc)

    # With enemy-only ZOC blocked, the 2-hex retreat destination is not reachable.
    blocked_retreat = compute_retreat_destination_hexes(
        st, "u", required_steps=2, movement_budget=2.0, blocked_hexes=blocked
    )
    assert dest not in blocked_retreat

    # Add a friendly unit adjacent to `mid` so that `mid` is also in friendly ZOC.
    friend_adj_mid = Hex(2, -1, -1)
    st2 = st.with_board(st.board.with_unit(UnitState("f", "inf", "union", friend_adj_mid, active=True)))
    enemy_zoc2 = adjacent_enemy_zoc_hexes(st2, "u")
    friendly_zoc2 = adjacent_friendly_zoc_hexes(st2, "u")
    assert mid in enemy_zoc2
    assert mid in friendly_zoc2
    blocked2 = frozenset(h for h in enemy_zoc2 if h not in friendly_zoc2)

    ok_retreat = compute_retreat_destination_hexes(
        st2, "u", required_steps=2, movement_budget=2.0, blocked_hexes=blocked2
    )
    assert dest in ok_retreat
