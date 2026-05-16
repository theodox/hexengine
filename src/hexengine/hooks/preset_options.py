"""
Preset bundles for hook contracts that select among engine-owned implementations.
"""

from __future__ import annotations

from types import SimpleNamespace


class PresetOptions(SimpleNamespace):
    """Keyword-named engine callables grouped for preset-style hook contracts.

    Subclassing `SimpleNamespace` allows `isinstance(x, PresetOptions)` checks
    when validating hook registration. Grouping callables in a PresetOptions instance
    allows for convenient lookup by keyword. For example, on the engine side
    we can declare a preset options bundle like this:
    MOVEMENT = PresetOptions(FAST=_fast_move, MEDIUM=_medium_move, SLOW=_slow_move)

    And on the title side we can bind a hook to a preset like this:

    @hook(contract=PRESET, presets=MOVEMENT, preset_attr="speed")
    def movement_budget_for_unit(state: GameState, unit_id: str) -> float:
        return MOVEMENT.FAST(state, unit_id)

    """


__all__ = ["PresetOptions"]
