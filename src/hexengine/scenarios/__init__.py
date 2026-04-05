from __future__ import annotations

from .loader import scenario_to_initial_state, scenario_to_legacy_scenario
from .parse import (
    default_scenario_path,
    load_scenario,
    resolve_map_background_url,
    resolve_scenario_path_for_server,
)
from .schema import (
    DEFAULT_GLOBAL_BASE_CSS_FILE,
    GlobalStylesConfig,
    MapDisplayConfig,
    ScenarioData,
    UnitGraphicsTemplate,
    default_global_styles_unresolved,
)

_HAS_LEGACY: bool
try:
    from .base import LocationItem, Scenario, ScenarioItem

    _HAS_LEGACY = True
except ImportError:
    # Server/runtime without Pyodide/js should still allow scenario loading.
    Scenario = None  # type: ignore[misc, assignment]
    ScenarioItem = None  # type: ignore[misc, assignment]
    LocationItem = None  # type: ignore[misc, assignment]
    _HAS_LEGACY = False

__all__ = [
    "DEFAULT_GLOBAL_BASE_CSS_FILE",
    "GlobalStylesConfig",
    "MapDisplayConfig",
    "ScenarioData",
    "UnitGraphicsTemplate",
    "default_global_styles_unresolved",
    "load_scenario",
    "default_scenario_path",
    "resolve_scenario_path_for_server",
    "resolve_map_background_url",
    "scenario_to_initial_state",
    "scenario_to_legacy_scenario",
]

if _HAS_LEGACY:
    __all__.extend(["Scenario", "ScenarioItem", "LocationItem"])
