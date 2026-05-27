"""
Engine hook catalog: `@hook`-decorated defaults keyed by dotted `TitleHooks` paths.

Merged registry plus movement budget engine default registration.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any

from ...state import GameState
from ...state.logic import DEFAULT_MOVEMENT_BUDGET
from ..core import SINGLE_DEFAULT
from ..ui_primary_actions import default_primary_actions_for_viewer
from ..ui_interaction_panels import default_interaction_panels_for_viewer
from ..movement_advance import default_auto_advance_phase_after_move_spend
from ..ui_turn_action_dock import default_turn_action_dock_for_viewer
from .contracts import hook

_ENGINE_CATALOG: dict[str, Callable[..., Any]] = {}


def register_engine_catalog_hook(path: str, fn: Callable[..., Any]) -> None:
    """Register one catalog callable under a dotted path (`bundle.field`)."""

    if path in _ENGINE_CATALOG:
        msg = f"Engine hook catalog path {path!r} is already registered"
        raise ValueError(msg)
    _ENGINE_CATALOG[path] = fn


def get_engine_catalog_hook(path: str) -> Callable[..., Any] | None:
    """Return the catalog callable for `path`, or `None` if unknown."""

    return _ENGINE_CATALOG.get(path)


def engine_catalog_map() -> Mapping[str, Callable[..., Any]]:
    """Immutable view of all registered catalog paths and callables."""

    return dict(_ENGINE_CATALOG)


def iter_engine_catalog_paths() -> Iterator[str]:
    yield from sorted(_ENGINE_CATALOG)


def _engine_impl_default_movement_budget_for_unit(
    _state: GameState, _unit_id: str
) -> float:
    """Budget per move when the title omits `movement_budget_for_unit`."""

    return float(DEFAULT_MOVEMENT_BUDGET)


movement_budget_for_unit_engine_default = hook(
    contract=SINGLE_DEFAULT,
    engine_impl=_engine_impl_default_movement_budget_for_unit,
)(_engine_impl_default_movement_budget_for_unit)


primary_actions_for_viewer_engine_default = hook(
    contract=SINGLE_DEFAULT,
    engine_impl=default_primary_actions_for_viewer,
    title_field="ui.primary_actions_for_viewer",
)(default_primary_actions_for_viewer)

interaction_panels_for_viewer_engine_default = hook(
    contract=SINGLE_DEFAULT,
    engine_impl=default_interaction_panels_for_viewer,
    title_field="ui.interaction_panels_for_viewer",
)(default_interaction_panels_for_viewer)

turn_action_dock_for_viewer_engine_default = hook(
    contract=SINGLE_DEFAULT,
    engine_impl=default_turn_action_dock_for_viewer,
    title_field="ui.turn_action_dock_for_viewer",
)(default_turn_action_dock_for_viewer)

auto_advance_phase_after_move_spend_engine_default = hook(
    contract=SINGLE_DEFAULT,
    engine_impl=default_auto_advance_phase_after_move_spend,
    title_field="movement.auto_advance_phase_after_move_spend",
)(default_auto_advance_phase_after_move_spend)


def _load_defaults() -> None:
    register_engine_catalog_hook(
        "movement.movement_budget_for_unit",
        movement_budget_for_unit_engine_default,
    )
    register_engine_catalog_hook(
        "ui.primary_actions_for_viewer",
        primary_actions_for_viewer_engine_default,
    )
    register_engine_catalog_hook(
        "ui.interaction_panels_for_viewer",
        interaction_panels_for_viewer_engine_default,
    )
    register_engine_catalog_hook(
        "ui.turn_action_dock_for_viewer",
        turn_action_dock_for_viewer_engine_default,
    )
    register_engine_catalog_hook(
        "movement.auto_advance_phase_after_move_spend",
        auto_advance_phase_after_move_spend_engine_default,
    )


_load_defaults()

__all__ = [
    "engine_catalog_map",
    "get_engine_catalog_hook",
    "iter_engine_catalog_paths",
    "auto_advance_phase_after_move_spend_engine_default",
    "interaction_panels_for_viewer_engine_default",
    "movement_budget_for_unit_engine_default",
    "primary_actions_for_viewer_engine_default",
    "turn_action_dock_for_viewer_engine_default",
    "register_engine_catalog_hook",
]
