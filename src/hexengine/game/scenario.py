from ..map.unit_layer import UnitLayer
from ..units import CanuckUnit, GenericUnit
from ..hexes.types import Hex
from ..map import Map
import logging

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


    def populate(self, map: Map):
        for member in self.units:
            member.cls.GRAPHICS_CREATOR.register()
            unit = member.cls.create(member.unit_id, member.unit_type, map)
            unit.position = member.position
            unit.display.set_text(member.unit_id[-4:])
            map.add_unit(unit)
            unit.visible = member.visible   
            
TEST_SCENARIO = Scenario(
    name="Test Scenario",
    description="A simple test scenario for the game.",
    units=[
        ScenarioItem(Hex(9, 2, -11), CanuckUnit, "Canuck1", "canuck"),
        ScenarioItem(Hex(7, 3, -10), GenericUnit, "Generic1", "soldier"),
        ScenarioItem(Hex(6, 4, -10), GenericUnit, "Generic2", "soldier", False),
    ]
)
