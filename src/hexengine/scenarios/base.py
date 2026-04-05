from typing import TYPE_CHECKING

from ..hexes.types import Hex
from ..map.location_item import LocationItem

if TYPE_CHECKING:
    from ..game import Game
    from ..units.game import GameUnit


class ScenarioItem:
    def __init__(
        self,
        pos: Hex,
        cls: type["GameUnit"],
        unit_id: str,
        unit_type: str,
        active: bool = True,
    ) -> None:
        self.cls = cls
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.position: Hex = pos
        self.active = active


class Scenario:
    def __init__(
        self,
        name: str,
        description: str,
        units: list[ScenarioItem],
        locations: list[LocationItem] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.units = units
        self.locations = locations if locations is not None else []

    def populate(self, game: "Game") -> None:
        for member in self.units:
            member.cls.GRAPHICS_CREATOR.register()
            unit = member.cls.create(member.unit_id, member.unit_type, game.canvas)
            unit.position = member.position
            unit.display.set_text(member.unit_id[-4:])
            unit.active = member.active
            game.add_unit(unit)

        for loc in self.locations:
            from ..map.location import Location

            location = Location.create(loc, game)
            game.board.add_location(location)
