"""Template title hooks — extend with modification, interaction, and ui modules as the title grows."""

from __future__ import annotations

from hexengine.arcs.registry import TurnArcRegistry
from hexengine.hooks.title import TitleHooks
from hexengine.hooks.wiring import assemble_title_hooks


def build_hooks(turn_registry: TurnArcRegistry | None = None) -> TitleHooks:
    if turn_registry is None:
        from ..turn_arc_schedule import build_template_turn_arc_registry

        turn_registry = build_template_turn_arc_registry()
    arcs_override = {"turn_arc_registry": lambda: turn_registry}
    return assemble_title_hooks(arcs=arcs_override)


__all__ = ["build_hooks"]
