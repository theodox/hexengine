from ...document import js
from ...units import GameUnit
from ...units.graphics import DisplayUnit, GraphicsCreator


class CanuckGraphicsCreator(GraphicsCreator):
    BASE_CLASSES = ("unit", "canuck")

    def create(self, display_unit: DisplayUnit):
        # Implement specific graphics creation for Canuck units
        display_unit.push_classes(*self.BASE_CLASSES)

        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")
        with self._attach(display_unit, rect, "canuck"):
            pass  # Position and size now handled by CSS

        flag = js.document.createElementNS("http://www.w3.org/2000/svg", "image")
        with self._attach(display_unit, flag, "canuck-flag"):
            flag.setAttributeNS(
                "http://www.w3.org/1999/xlink", "href", "resources/canada.png"
            )

        return display_unit

    _CSS = """
.canuck rect {
    fill: rgb(135, 13, 2);
    stroke: rgba(0, 0, 0, 0.25);
}

.canuck:hover rect {
    fill: rgb(177, 98, 1);
}

.canuck.hilited rect {
    fill: rgb(255, 57, 57);
}

.canuck-flag {
    x: calc(-1 * var(--unit-half-width));
    y: calc(-1 * var(--unit-half-height));
    width: var(--unit-width);
    height: var(--unit-height);
"""


class CanuckUnit(GameUnit):
    FACTION: str = "canadian"
    GRAPHICS_CREATOR: GraphicsCreator = CanuckGraphicsCreator
    """A game unit with logic and state, using the CanuckGraphicsCreator for display."""
