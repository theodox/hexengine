"""
GraphicsCreator subclasses built from scenario ``unit_graphics`` wire payloads.

Re-exported from :mod:`hexengine.client.svg_templates` so ``marker_graphics`` can
use the same template parsing / caching as units (type → template → instances).
"""

from __future__ import annotations

from .svg_templates import (
    DisplayCreator,
    creator_for_template,
    display_creator_from_class,
)

# Aliases for callers; assignments satisfy Ruff F401 on re-exports.
UnitDisplayCreator = DisplayCreator
graphics_creator_for_template = creator_for_template
unit_display_creator_from_class = display_creator_from_class

__all__ = [
    "UnitDisplayCreator",
    "graphics_creator_for_template",
    "unit_display_creator_from_class",
]
