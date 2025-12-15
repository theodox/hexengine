from ...hexes.types import Hex
from ..game import Game



class ScenarioItem:
    def __init__(self, pos, cls, unit_id, unit_type, visible=True):
        self.cls = cls
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.position: Hex = pos
        self.visible = visible


class Scenario:
    def __init__(self, name, description, units: list[ScenarioItem]):
        self.name = name
        self.description = description
        self.units = units

    def populate(self, game:Game):
        for member in self.units:
            member.cls.GRAPHICS_CREATOR.register()
            unit = member.cls.create(member.unit_id, member.unit_type, game.canvas)
            unit.position = member.position
            unit.display.set_text(member.unit_id[-4:])
            unit.visible = member.visible
            game.add_unit(unit)