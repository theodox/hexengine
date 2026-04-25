"""Optional ``GameDefinition`` hooks for title-defined per-unit ``UnitState.attributes``."""

from __future__ import annotations

from typing import Any

from ..state.game_state import GameState
from .protocol import GameDefinition


def default_attributes_for_unit_type(
    game: GameDefinition, unit_type: str
) -> dict[str, Any]:
    """
    Get the default attributes for a unit type.

    If the game definition <game> has a default_attributes_for_unit_type method, use it.
    Otherwise, return an empty dictionary.
    """
    fn = getattr(game, "default_attributes_for_unit_type", None)
    if callable(fn):
        out = fn(unit_type)
        return dict(out) if isinstance(out, dict) else {}
    return {}


def merge_spawn_attributes(
    game: GameDefinition,
    unit_type: str,
    instance_attrs: dict[str, Any] | None,
    *,
    state: GameState | None = None,
) -> dict[str, Any]:
    fn = getattr(game, "merge_spawn_attributes", None)
    if callable(fn):
        out = fn(unit_type, dict(instance_attrs or {}), state)
        return dict(out) if isinstance(out, dict) else {}
    base = default_attributes_for_unit_type(game, unit_type)
    return {**base, **(instance_attrs or {})}


def validate_unit_attributes_patch(
    game: GameDefinition,
    state: GameState,
    unit_id: str,
    patch: dict[str, Any],
) -> None:
    fn = getattr(game, "validate_unit_attributes_patch", None)
    if callable(fn):
        fn(state, unit_id, patch)
