import js
from .graphics import GraphicsCreator, DisplayUnit
from . import GameUnit


class CanuckGraphicsCreator(GraphicsCreator):
    BASE_CLASSES = ("unit", "canuck")
 

    def create(self, display_unit: DisplayUnit):
        # Implement specific graphics creation for Canuck units
        display_unit.push_classes(*self.BASE_CLASSES)
        w, h = self._get_unit_size(display_unit)

        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")   
        with self._attach(display_unit, rect, "canuck"):
            rect.setAttribute("x", -w // 2)
            rect.setAttribute("y", -h // 2)
            rect.setAttribute("width", w)
            rect.setAttribute("height", h)
        
        flag = js.document.createElementNS("http://www.w3.org/2000/svg", "image")
        with self._attach(display_unit, flag, "canuck-flag"):
            flag.setAttribute("x", -w // 2)
            flag.setAttribute("y", -h // 2)
            flag.setAttribute("width", w)
            flag.setAttribute("height", h)
            flag.setAttributeNS(
                "http://www.w3.org/1999/xlink", "href", "resources/canada.png"
            )
        
        return display_unit

    @classmethod
    def register(cls):
        if not cls.STYLE_CREATED:
            style = js.document.createElement("style")
            style.textContent = """
            .canuck rect {
                fill: rgb(135, 13, 2);
                stroke: rgba(0, 0, 0, 0.25);
            }

            .canuck:hover rect {
                fill: rgb(177, 98, 1);
            }

            .canuck.active rect {
                fill: rgb(255, 57, 57);
            }
            """
            js.document.head.appendChild(style)

        cls.STYLE_CREATED = True


class CanuckUnit(GameUnit):
    GRAPHICS_CREATOR: GraphicsCreator = CanuckGraphicsCreator
    """A game unit with logic and state, using the CanuckGraphicsCreator for display."""
