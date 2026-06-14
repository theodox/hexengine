"""Template title hooks — extend with modification, interaction, and ui modules as the title grows."""

from __future__ import annotations

from hexengine.hooks.title import TitleHooks
from hexengine.hooks.wiring import assemble_title_hooks

from . import arcs


def build_hooks() -> TitleHooks:
    return assemble_title_hooks(arcs)


__all__ = ["build_hooks"]
