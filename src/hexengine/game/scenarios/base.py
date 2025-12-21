from ...hexes.types import Hex
from ..game import Game
from ...map.location import Location


class ScenarioItem:
    def __init__(self, pos, cls, unit_id, unit_type, active=True):
        self.cls = cls
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.position: Hex = pos
        self.active = active


class LocationItem:
    def __init__(self, pos, loc_type, movement_cost):
        self.position: Hex = pos
        self.movement_cost = movement_cost
        self.type = loc_type


class Scenario:
    def __init__(
        self,
        name,
        description,
        units: list[ScenarioItem],
        locations: list[LocationItem] = [],
    ):
        self.name = name
        self.description = description
        self.units = units
        self.locations = locations

    def populate(self, game: Game):
        for member in self.units:
            member.cls.GRAPHICS_CREATOR.register()
            unit = member.cls.create(member.unit_id, member.unit_type, game.canvas)
            unit.position = member.position
            unit.display.set_text(member.unit_id[-4:])
            unit.active = member.active
            game.add_unit(unit)

        for loc in self.locations:
            location = Location.create(loc, game)
            game.board.add_location(location)
