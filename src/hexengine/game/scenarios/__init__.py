from .loader import scenario_to_initial_state, scenario_to_legacy_scenario
from .parse import default_scenario_path, load_scenario
from .schema import ScenarioData

try:
    from .base import Scenario, ScenarioItem, LocationItem
    _HAS_LEGACY = True
except ImportError:
    # Server/runtime without Pyodide/js should still allow scenario loading.
    Scenario = None  # type: ignore[misc, assignment]
    ScenarioItem = None  # type: ignore[misc, assignment]
    LocationItem = None  # type: ignore[misc, assignment]
    _HAS_LEGACY = False

__all__ = [
    "ScenarioData",
    "load_scenario",
    "default_scenario_path",
    "scenario_to_initial_state",
    "scenario_to_legacy_scenario",
]

if _HAS_LEGACY:
    __all__.extend(["Scenario", "ScenarioItem", "LocationItem"])
