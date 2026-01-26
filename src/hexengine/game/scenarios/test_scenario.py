from ...hexes.types import Hex
from .base import Scenario, ScenarioItem, LocationItem
from .canuck import CanuckUnit
from .generic import GenericUnit


TEST_SCENARIO = Scenario(
    name="Test Scenario",
    description="A simple test scenario for the game.",
    units=[
        ScenarioItem(Hex(16, 4, -20), CanuckUnit, "Canuck1", "canuck"),
        ScenarioItem(Hex(16, 5, -21), CanuckUnit, "Canuck2", "canuck"),
        ScenarioItem(Hex(16, 6, -22), CanuckUnit, "Canuck3", "canuck"),
        ScenarioItem(Hex(7, 3, -10), GenericUnit, "Generic1", "soldier"),
        ScenarioItem(Hex(6, 4, -10), GenericUnit, "Generic2", "soldier"),
        ScenarioItem(Hex(8, 4, -12), GenericUnit, "Generic3", "soldier"),
    ],
    locations=[
        LocationItem(Hex(5, 5, -10), "forest", 1.5, 1.5, 1.5, True),
        LocationItem(Hex(10, 2, -12), "hill", 3.0, 2.0, 0.0, True),
        LocationItem(Hex(8, 2, -10), "hill", 3.0, 2.0, 0.0, True),
        LocationItem(Hex(9, 4, -13), "forest", 1.5, 1.5, 1.5, True),
        LocationItem(Hex(6, 2, -8), "forest", 1.5, 1.5, 1.5, True),
        LocationItem(Hex(6, 3, -9), "forest", 1.5, 1.5, 1.5, True),
        LocationItem(Hex(6, 5, -11), "water", float("inf"), 0.0, 0.0, True),
        LocationItem(Hex(7, 5, -12), "water", float("inf"), 0.0, 0.0, True),
        LocationItem(Hex(7, 4, -11), "water", float("inf"), 0.0, 0.0, True),
        LocationItem(Hex(8, 4, -12), "water", float("inf"), 0.0, 0.0, True),
    ],
)
