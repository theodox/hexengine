"""
Map ScenarioData onto current game types.

This is the only place that ties the scenario DSL to UnitState, LocationState,
ScenarioItem, LocationItem, etc. When those change, only this file changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..hexes.types import Hex, HexRowCol
from ..state import GameState
from ..state.game_state import BoardState, LocationState, UnitState
from .schema import ScenarioData

if TYPE_CHECKING:
    from ..units.game import GameUnit
    from .base import Scenario


def _hex(pos: tuple[int, int]) -> Hex:
    """Scenario ``Position`` is odd-q ``(col, row)``."""
    return Hex.from_hex_row_col(HexRowCol(col=pos[0], row=pos[1]))


def scenario_to_initial_state(
    data: ScenarioData,
    initial_faction: str = "Red",
    initial_phase: str = "Movement",
    phase_actions_remaining: int = 2,
) -> GameState:
    """
    Build an initial GameState from scenario data (server path).

    Does not use ActionManager — constructs state directly. When BoardState
    or UnitState/LocationState change, update only this function.
    """
    from ..state.game_state import TurnState

    board = BoardState()
    turn = TurnState(
        current_faction=initial_faction,
        current_phase=initial_phase,
        phase_actions_remaining=phase_actions_remaining,
        turn_number=1,
    )

    for loc in data.locations:
        board = board.with_location(
            LocationState(
                position=_hex(loc.position),
                terrain_type=loc.terrain_type,
                movement_cost=loc.movement_cost,
                hex_color=loc.hex_color,
            )
        )

    for u in data.units:
        board = board.with_unit(
            UnitState(
                unit_id=u.unit_id,
                unit_type=u.unit_type,
                faction=u.faction,
                position=_hex(u.position),
                health=u.health,
                active=u.active,
            )
        )

    return GameState(board=board, turn=turn)


def scenario_to_legacy_scenario(
    data: ScenarioData,
    unit_registry: dict[str, type[GameUnit]],
) -> Scenario:
    """
    Build the legacy Scenario (ScenarioItem + LocationItem) for populate(game).

    unit_registry maps type strings to classes, e.g. {"canuck": CanuckUnit, "soldier": GenericUnit}.
    When Scenario / ScenarioItem / LocationItem change, update only this function.
    """
    from ..map.location_item import LocationItem
    from .base import Scenario, ScenarioItem

    units = []
    for u in data.units:
        cls = unit_registry.get(u.unit_type)
        if cls is None:
            raise KeyError(f"Unknown unit type in scenario: {u.unit_type!r}")
        units.append(
            ScenarioItem(
                pos=_hex(u.position),
                cls=cls,
                unit_id=u.unit_id,
                unit_type=u.unit_type,
                active=u.active,
            )
        )

    locations = [
        LocationItem(
            _hex(loc.position),
            loc.terrain_type,
            loc.movement_cost,
            loc.assault_modifier,
            loc.ranged_modifier,
            loc.block_los,
            loc.hex_color,
        )
        for loc in data.locations
    ]

    return Scenario(
        name=data.name,
        description=data.description,
        units=units,
        locations=locations,
    )
