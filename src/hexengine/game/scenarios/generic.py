import js
from ...units.graphics import GraphicsCreator, DisplayUnit
from ...units import GameUnit


class GenericGraphicsCreator(GraphicsCreator):
    BASE_CLASSES = ("soldier", "unit")

    def create(self, display_unit: DisplayUnit):
        display_unit.push_classes(*self.BASE_CLASSES)

        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")
        with self._attach(display_unit, rect):
            pass  # Position and size now handled by CSS

        c = js.document.createElementNS("http://www.w3.org/2000/svg", "circle")
        with self._attach(display_unit, c, "soldier-center"):
            pass  # Radius now handled by CSS

        t = js.document.createElementNS("http://www.w3.org/2000/svg", "text")
        with self._attach(display_unit, t, "soldier-text"):
            display_unit.set_text_element(t)

        return display_unit

    _CSS = """
.soldier rect {
    fill: rgb(118, 161, 82);
    stroke: rgba(0, 0, 0, 0.25);
    width: calc(var(--unit-width) - 2px);
    height: calc(var(--unit-height) - 2px);
}

.soldier:hover rect {
    fill: rgb(134, 130, 82);
}

.soldier.hilited rect {
    fill: rgb(255, 243, 110);
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
    GRAPHICS_CREATOR: GraphicsCreator = GenericGraphicsCreator
    """A game unit with logic and state, using the GenericGraphicsCreator for display."""
