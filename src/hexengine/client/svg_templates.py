"""
SVG/template graphics helpers shared by units and markers.

This extracts the "template wire dict -> GraphicsCreator subclass -> callable(create)" path
so we can reuse it for non-unit counters (markers) without duplicating DOM code.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..document import js
from ..units.graphics import DisplayUnit, GraphicsCreator

_UNIT_SIZE_DIVISOR = 1.5
_SVG_NS = "http://www.w3.org/2000/svg"

_REGISTERED_STYLE_KEYS: set[str] = set()
_SVG_IMAGE_CLASS_CACHE: dict[str, type] = {}
_INLINE_SVG_CLASS_CACHE: dict[str, type] = {}
_SVG_FILE_INLINE_CLASS_CACHE: dict[str, type] = {}

DisplayCreator = Callable[[DisplayUnit], None]


def display_creator_from_class(cls: type, *, name: str) -> DisplayCreator:
    def fn(display_unit: DisplayUnit) -> None:
        cls.register()
        cls().create(display_unit)

    setattr(fn, "name", name)
    return fn


def _register_template_styles_once(key: str, css: str | None, css_href: str | None) -> None:
    if key in _REGISTERED_STYLE_KEYS:
        return
    if css_href:
        link = js.document.createElement("link")
        link.rel = "stylesheet"
        link.href = css_href
        js.document.head.appendChild(link)
    if css:
        style = js.document.createElement("style")
        style.setAttribute("data-hexes-template", key[:120])
        style.innerHTML = css
        js.document.head.appendChild(style)
    _REGISTERED_STYLE_KEYS.add(key)


def _sync_fetch_text(url: str) -> str:
    xhr = js.XMLHttpRequest.new()
    xhr.open("GET", url, False)
    xhr.send(None)
    status = int(xhr.status)
    text = str(xhr.responseText or "")
    if status and (status < 200 or status >= 300):
        raise OSError(f"Failed to load {url!r}: HTTP {status}")
    if not text.strip():
        raise OSError(f"Empty response for {url!r}")
    return text


def _append_parsed_svg_markup(display_unit: DisplayUnit, svg_markup: str) -> None:
    parser = js.DOMParser.new()
    doc = parser.parseFromString(svg_markup, "image/svg+xml")
    root = doc.documentElement
    if root is None:
        return
    tag = str(root.tagName).lower()
    if tag == "svg":
        children = root.children
        n = int(children.length)
        for i in range(n):
            child = children.item(i)
            if child is not None:
                display_unit.proxy.appendChild(js.document.importNode(child, True))
    else:
        display_unit.proxy.appendChild(js.document.importNode(root, True))


def _svg_image_file_class(href: str, css: str | None, css_href: str | None) -> type:
    cache_key = f"img:{href}|{css or ''}|{css_href or ''}"
    cached = _SVG_IMAGE_CLASS_CACHE.get(cache_key)
    if cached is not None:
        return cached
    href_local = href
    sk = cache_key

    class SvgFileImageTemplateGraphics(GraphicsCreator):
        BASE_CLASSES = ("unit", "unit-svg-template")
        STYLE_CREATED = True

        @classmethod
        def register(cls) -> None:
            _register_template_styles_once(sk, css, css_href)

        def create(self, display_unit: DisplayUnit) -> DisplayUnit:
            display_unit.push_classes(*self.BASE_CLASSES)
            layout = display_unit._hex_layout
            unit_size = int(layout.size * _UNIT_SIZE_DIVISOR) if layout else 30
            half = unit_size / 2
            img = js.document.createElementNS(_SVG_NS, "image")
            with self._attach(display_unit, img, "unit-svg-template-img"):
                img.setAttributeNS("http://www.w3.org/1999/xlink", "href", href_local)
                img.setAttribute("x", str(-half))
                img.setAttribute("y", str(-half))
                img.setAttribute("width", str(unit_size))
                img.setAttribute("height", str(unit_size))
            return display_unit

    _SVG_IMAGE_CLASS_CACHE[cache_key] = SvgFileImageTemplateGraphics
    return SvgFileImageTemplateGraphics


def _inline_svg_markup_class(
    svg_markup: str,
    *,
    css: str | None,
    css_href: str | None,
    cache_key: str,
) -> type:
    cached = _INLINE_SVG_CLASS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    markup = svg_markup
    sk = cache_key

    class InlineSvgTemplateGraphics(GraphicsCreator):
        BASE_CLASSES = ("unit", "unit-svg-inline-template")
        STYLE_CREATED = True

        @classmethod
        def register(cls) -> None:
            _register_template_styles_once(sk, css, css_href)

        def create(self, display_unit: DisplayUnit) -> DisplayUnit:
            display_unit.push_classes(*self.BASE_CLASSES)
            _append_parsed_svg_markup(display_unit, markup)
            return display_unit

    _INLINE_SVG_CLASS_CACHE[cache_key] = InlineSvgTemplateGraphics
    return InlineSvgTemplateGraphics


def creator_for_template(tmpl: dict[str, Any]) -> DisplayCreator | None:
    render = str(tmpl.get("render", "image")).lower()
    css = tmpl.get("css")
    css = str(css).strip() if css else None
    cf = tmpl.get("css_file")
    css_href = str(cf).strip() if cf else None

    if render == "counter":
        from ..scenarios.generic_counter import make_counter_graphics_creator

        def _wire_color(key: str) -> str | None:
            v = tmpl.get(key)
            if v is None:
                return None
            s = str(v).strip()
            return s if s else None

        g = tmpl.get("glyph")
        c = tmpl.get("caption")
        glyph = "\u25c7" if g is None else str(g)
        caption = "" if c is None else str(c)
        cls = make_counter_graphics_creator(
            glyph,
            caption,
            extra_css=css,
            extra_css_href=css_href,
            counter_fill=_wire_color("counter_fill"),
            counter_fill_hover=_wire_color("counter_fill_hover"),
            counter_fill_hilite=_wire_color("counter_fill_hilite"),
        )
        return display_creator_from_class(
            cls, name=f"counter({tmpl.get('type','?')},{glyph!r},{caption!r})"
        )

    svg_file = tmpl.get("svg_file")
    if svg_file:
        sf = str(svg_file)
        if render == "image":
            cls = _svg_image_file_class(sf, css, css_href)
            return display_creator_from_class(cls, name=f"svg_image({sf})")
        if render == "inline":
            ck = f"file-inline:{sf}|{css or ''}|{css_href or ''}"
            cached = _SVG_FILE_INLINE_CLASS_CACHE.get(ck)
            if cached is not None:
                return display_creator_from_class(
                    cached, name=f"svg_inline_file_cached({sf})"
                )
            text = _sync_fetch_text(sf)
            cls = _inline_svg_markup_class(
                text,
                css=css,
                css_href=css_href,
                cache_key=ck + f"|h{hash(text) & 0xFFFFFFFF:x}",
            )
            _SVG_FILE_INLINE_CLASS_CACHE[ck] = cls
            return display_creator_from_class(cls, name=f"svg_inline_file({sf})")

    raw_svg = tmpl.get("svg")
    if raw_svg and render == "inline":
        text = str(raw_svg)
        ck = f"inline:{hash(text) & 0xFFFFFFFF:x}|{css or ''}|{css_href or ''}"
        cls = _inline_svg_markup_class(text, css=css, css_href=css_href, cache_key=ck)
        return display_creator_from_class(cls, name="svg_inline(markup)")

    return None

