from __future__ import annotations

from ..hexes.types import Hex
from .base import LocationItem, Scenario, ScenarioItem
from .canuck import CanuckUnit
from .generic import GenericUnit

TEST_SCENARIO: Scenario = Scenario(
    name="Test Scenario",
    description="Legacy mirror of data/test_scenario/scenario.toml (subset of terrain).",
    units=[
        ScenarioItem(Hex(0, 0, 0), CanuckUnit, "Canuck1", "canuck"),
        ScenarioItem(Hex(1, 0, -1), CanuckUnit, "Canuck2", "canuck"),
        ScenarioItem(Hex(2, 0, -2), CanuckUnit, "Canuck3", "canuck"),
        ScenarioItem(Hex(7, 0, -7), GenericUnit, "Generic1", "soldier"),
        ScenarioItem(Hex(7, 1, -8), GenericUnit, "Generic2", "soldier"),
        ScenarioItem(Hex(7, 2, -9), GenericUnit, "Generic3", "soldier"),
    ],
    locations=[
        LocationItem(Hex(3, 2, -5), "beach", 1.5, 0.0, 0.0, True),
        LocationItem(Hex(2, 2, -4), "evergreen-hills", 2.5, 0.0, 0.0, True),
        LocationItem(Hex(5, 2, -7), "ocean", float("inf"), 0.0, 0.0, True),
        LocationItem(Hex(0, 5, -5), "plain", 1.0, 0.0, 0.0, True),
    ],
)
