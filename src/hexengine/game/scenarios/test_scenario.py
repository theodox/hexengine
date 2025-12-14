from ...hexes.types import Hex
from . import Scenario, ScenarioItem
from .canuck import CanuckUnit
from .generic import GenericUnit


TEST_SCENARIO = Scenario(
    name="Test Scenario",
    description="A simple test scenario for the game.",
    units=[
        ScenarioItem(Hex(9, 2, -11), CanuckUnit, "Canuck1", "canuck"),
        ScenarioItem(Hex(7, 3, -10), GenericUnit, "Generic1", "soldier"),
        ScenarioItem(Hex(6, 4, -10), GenericUnit, "Generic2", "soldier", False),
        ScenarioItem(Hex(8, 4, -12), GenericUnit, "Generic3", "soldier", True),
    ]
)
