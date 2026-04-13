"""
Square SVG unit counter: nested viewBox, CSS fill/glyph/caption, factory for per-type defaults.
"""

from __future__ import annotations

from ..document import js
from ..map.layout import unit_display_pixel_size
from ..units.graphics import DisplayUnit, GraphicsCreator

_SVG_NS = "http://www.w3.org/2000/svg"

# Shared stylesheet injected once (factory may produce many subclasses with identical CSS).
_COUNTER_CSS_IN_HEAD = False
_COUNTER_EXTRA_STYLE_SIGS: set[tuple[str, str]] = set()
_COUNTER_BASE_CSS_HREF = "resources/default/unit_counter.css"


def _ensure_counter_css_in_document() -> None:
    global _COUNTER_CSS_IN_HEAD
    if _COUNTER_CSS_IN_HEAD:
        return
    link = js.document.createElement("link")
    link.rel = "stylesheet"
    link.href = _COUNTER_BASE_CSS_HREF
    js.document.head.appendChild(link)
    _COUNTER_CSS_IN_HEAD = True


def _strip_color(value: str | None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def make_counter_graphics_creator(
    glyph_text: str = "\u25c7",
    caption_text: str = "",
    *,
    extra_css: str | None = None,
    extra_css_href: str | None = None,
    counter_fill: str | None = None,
    counter_fill_hover: str | None = None,
    counter_fill_hilite: str | None = None,
) -> type:
    """
    Build a `GraphicsCreator` subclass with fixed glyph/caption strings.

    CSS is registered once in the document; each subclass only differs in initial text.
    Optional `extra_css` / `extra_css_href` come from scenario `[[unit_graphics]]`
    (e.g. faction tints) and are injected once per distinct pair.
    """

    g0 = glyph_text
    c0 = caption_text
    xcss = extra_css.strip() if extra_css else ""
    xhref = extra_css_href.strip() if extra_css_href else ""
    f_fill = _strip_color(counter_fill)
    f_hover = _strip_color(counter_fill_hover)
    f_hilite = _strip_color(counter_fill_hilite)
    extra_sig = (xcss, xhref)

    class CounterUnitGraphics(GraphicsCreator):
        """Dynamic counter graphics (glyph/caption closed over at class creation)."""

        BASE_CLASSES = ("unit", "unit-counter")
        STYLE_CREATED = True

        @classmethod
        def register(cls) -> None:
            _ensure_counter_css_in_document()
            if extra_sig != ("", "") and extra_sig not in _COUNTER_EXTRA_STYLE_SIGS:
                _COUNTER_EXTRA_STYLE_SIGS.add(extra_sig)
                if xhref:
                    link = js.document.createElement("link")
                    link.rel = "stylesheet"
                    link.href = xhref
                    js.document.head.appendChild(link)
                if xcss:
                    st = js.document.createElement("style")
                    st.innerHTML = xcss
                    js.document.head.appendChild(st)

        def create(self, display_unit: DisplayUnit) -> DisplayUnit:
            display_unit.push_classes(*self.BASE_CLASSES)

            layout = display_unit._hex_layout
            unit_size = (
                unit_display_pixel_size(layout.size, display_unit.unit_size_multiplier)
                if layout
                else 30
            )
            half = unit_size / 2.0

            inner = js.document.createElementNS(_SVG_NS, "svg")
            with self._attach(display_unit, inner, "unit-counter-root"):
                inner.setAttribute("viewBox", "0 0 100 100")
                inner.setAttribute("width", str(unit_size))
                inner.setAttribute("height", str(unit_size))
                inner.setAttribute("x", str(-half))
                inner.setAttribute("y", str(-half))

            rect = js.document.createElementNS(_SVG_NS, "rect")
            rect.setAttribute("x", "0")
            rect.setAttribute("y", "0")
            rect.setAttribute("width", "100")
            rect.setAttribute("height", "100")
            rect.classList.add("unit-counter-base")
            rect.setAttribute("data-unit", display_unit.unit_id)
            inner.appendChild(rect)

            glyph_el = js.document.createElementNS(_SVG_NS, "text")
            glyph_el.setAttribute("x", "50")
            glyph_el.setAttribute("y", "33")
            glyph_el.classList.add("unit-counter-glyph")
            glyph_el.textContent = g0
            glyph_el.setAttribute("data-unit", display_unit.unit_id)
            inner.appendChild(glyph_el)

            cap_el = js.document.createElementNS(_SVG_NS, "text")
            cap_el.setAttribute("x", "50")
            cap_el.setAttribute("y", "83")
            cap_el.classList.add("unit-counter-caption")
            cap_el.textContent = c0
            cap_el.setAttribute("data-unit", display_unit.unit_id)
            inner.appendChild(cap_el)

            display_unit.set_glyph_element(glyph_el)
            display_unit.set_caption_element(cap_el)
            # If caption was provided by the scenario/template, keep it static.
            # If caption is empty, reuse it as the health text sink.
            if not c0:
                display_unit.set_text_element(cap_el)

            st = display_unit.proxy.style
            if f_fill is not None:
                st.setProperty("--unit-counter-fill", f_fill)
            if f_hover is not None:
                st.setProperty("--unit-counter-fill-hover", f_hover)
            if f_hilite is not None:
                st.setProperty("--unit-counter-fill-hilite", f_hilite)

            return display_unit

    return CounterUnitGraphics


FallbackCounterGraphicsCreator = make_counter_graphics_creator("?", "DEBUG")
