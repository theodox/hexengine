"""Engine-only hook machinery (catalog, contracts).

Game titles should import from `hexengine.hooks.<movement|attack|ui|title|wiring>` instead.
"""

from __future__ import annotations

from .catalog import (
    engine_catalog_map,
    get_engine_catalog_hook,
    iter_engine_catalog_paths,
    movement_budget_for_unit_engine_default,
    register_engine_catalog_hook,
)
from .contracts import hook, validate_title_contract

__all__ = [
    "engine_catalog_map",
    "get_engine_catalog_hook",
    "hook",
    "iter_engine_catalog_paths",
    "movement_budget_for_unit_engine_default",
    "register_engine_catalog_hook",
    "validate_title_contract",
]
