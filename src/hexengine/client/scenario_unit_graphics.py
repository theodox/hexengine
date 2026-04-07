"""
GraphicsCreator subclasses built from scenario ``unit_graphics`` wire payloads.
"""

from __future__ import annotations

from typing import Any

from ..document import js
from ..units.graphics import DisplayUnit, GraphicsCreator

# Match CanuckGraphicsCreator / map unit sizing until layout exposes multiplier here.
_UNIT_SIZE_DIVISOR = 1.5

_SVG_IMAGE_CLASS_CACHE: dict[str, type] = {}


def _svg_image_file_class(href: str) -> type:
    cached = _SVG_IMAGE_CLASS_CACHE.get(href)
    if cached is not None:
        return cached
    href_local = href

    class SvgFileTemplateGraphics(GraphicsCreator):
        BASE_CLASSES = ("unit", "unit-svg-template")
        STYLE_CREATED = True

        def create(self, display_unit: DisplayUnit) -> DisplayUnit:
            display_unit.push_classes(*self.BASE_CLASSES)
            layout = display_unit._hex_layout
            unit_size = int(layout.size * _UNIT_SIZE_DIVISOR) if layout else 30
            half = unit_size / 2
            img = js.document.createElementNS("http://www.w3.org/2000/svg", "image")
            with self._attach(display_unit, img, "unit-svg-template-img"):
                img.setAttributeNS("http://www.w3.org/1999/xlink", "href", href_local)
                img.setAttribute("x", str(-half))
                img.setAttribute("y", str(-half))
                img.setAttribute("width", str(unit_size))
                img.setAttribute("height", str(unit_size))
            return display_unit

    _SVG_IMAGE_CLASS_CACHE[href] = SvgFileTemplateGraphics
    return SvgFileTemplateGraphics


def graphics_creator_class_for_template(tmpl: dict[str, Any]) -> type | None:
    """
    Map one template ``to_wire_dict()`` to a GraphicsCreator subclass, or None to
    fall back to built-in creators.
    """
    svg_file = tmpl.get("svg_file")
    render = str(tmpl.get("render", "image")).lower()
    if svg_file and render == "image":
        return _svg_image_file_class(str(svg_file))
    return None
