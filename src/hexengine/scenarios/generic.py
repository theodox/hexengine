from ..document import js
from ..units import GameUnit
from ..units.graphics import DisplayUnit, GraphicsCreator


class GenericGraphicsCreator(GraphicsCreator):
    BASE_CLASSES = ("soldier", "unit")

    def create(self, display_unit: DisplayUnit) -> DisplayUnit:
        display_unit.push_classes(*self.BASE_CLASSES)

        # Get unit size from layout
        unit_size = (
            int(display_unit._hex_layout.size * self.UNIT_SIZE_DIVISOR)
            if display_unit._hex_layout
            else 30
        )
        half_size = unit_size / 2

        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")
        with self._attach(display_unit, rect):
            rect.setAttribute("x", str(-half_size))
            rect.setAttribute("y", str(-half_size))
            rect.setAttribute("width", str(unit_size - 2))
            rect.setAttribute("height", str(unit_size - 2))

        c = js.document.createElementNS("http://www.w3.org/2000/svg", "circle")
        with self._attach(display_unit, c, "soldier-center"):
            c.setAttribute("cx", "0")
            c.setAttribute("cy", "0")
            c.setAttribute("r", str(unit_size / self.HEAD_RADIUS_DIVISOR))

        t = js.document.createElementNS("http://www.w3.org/2000/svg", "text")
        with self._attach(display_unit, t, "soldier-text"):
            display_unit.set_text_element(t)
            t.setAttribute("x", "0")
            t.setAttribute("y", str(unit_size / 3))

        return display_unit

    _CSS = """
.soldier rect {
    fill: rgb(118, 161, 82);
    stroke: rgba(0, 0, 0, 0.25);
    width: calc(var(--unit-width) - 2px);
    height: calc(var(--unit-height) - 2px);
    pointer-events: all;
}

.soldier:hover rect {
    fill: rgb(134, 130, 82);
}

.soldier.hilited rect {
    fill: rgb(255, 243, 110);
}

.soldier-center {
    pointer-events: all;
}

.soldier text {
    fill: rgba(34, 13, 13, 0.75);
    font-size: 8pt;
    text-anchor: middle;
    font-family: sans-serif;
    font-weight: bold;
    pointer-events: none;
    user-select: none;
    transform: translateY(calc(var(--unit-height) / 3));
}

.soldier-center {
    cy: -6px;
    r: calc(min(var(--unit-width), var(--unit-height)) / 5);
    fill: rgba(35, 54, 49, 0.75);
    pointer-events: none;
    user-select: none;
}

"""


class GenericUnit(GameUnit):
    FACTION: str = "Blue"
    GRAPHICS_CREATOR: GraphicsCreator = GenericGraphicsCreator
    """A game unit with logic and state, using the GenericGraphicsCreator for display."""
