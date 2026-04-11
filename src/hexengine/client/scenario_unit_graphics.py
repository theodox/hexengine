"""
GraphicsCreator subclasses built from scenario ``unit_graphics`` wire payloads.

Re-exported from :mod:`hexengine.client.svg_templates` so ``marker_graphics`` can
use the same template parsing / caching as units (type → template → instances).
"""

from __future__ import annotations

from .svg_templates import DisplayCreator as UnitDisplayCreator
from .svg_templates import creator_for_template as graphics_creator_for_template
from .svg_templates import display_creator_from_class as unit_display_creator_from_class
