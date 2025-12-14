import js
from .graphics import GraphicsCreator, DisplayUnit
from . import GameUnit


class GenericGraphicsCreator(GraphicsCreator):
    BASE_CLASSES = ("soldier", "unit")

    def create(self, display_unit: DisplayUnit):
        display_unit.push_classes(*self.BASE_CLASSES)
        w, h = self._get_unit_size(display_unit)

        rect = js.document.createElementNS("http://www.w3.org/2000/svg", "rect")
        with self._attach(display_unit, rect):
            rect.setAttribute("x", -w // 2)
            rect.setAttribute("y", -h // 2)
            rect.setAttribute("width", w - 2)
            rect.setAttribute("height", h - 2)
            

        c = js.document.createElementNS("http://www.w3.org/2000/svg", "circle")
        with self._attach(display_unit, c, "soldier-center"):
            c.setAttribute("r", str(min(w, h) // self.HEAD_RADIUS_DIVISOR))

        t = js.document.createElementNS("http://www.w3.org/2000/svg", "text")
        with self._attach(display_unit, t, "soldier-text"):
            t.setAttribute("x", "0")
            t.setAttribute("y", h // 3)
            display_unit.set_text_element(t)

        return display_unit

    @classmethod
    def register(cls):
        style = js.document.createElement("style")
        style.textContent = """
        .soldier rect {
            fill: rgb(118, 161, 82);
            stroke: rgba(0, 0, 0, 0.25);
        }

        .soldier:hover rect {
            fill: rgb(134, 130, 82);
        }

        .soldier.active rect {
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
        }

        .soldier-center {
            position: absolute;
            cy: -6px;
            
            fill: rgba(35, 54, 49, 0.75);
            pointer-events: none;
            user-select: none;
        }
        """
        js.document.head.appendChild(style)


class GenericUnit(GameUnit):
    GRAPHICS_CREATOR: GraphicsCreator = GenericGraphicsCreator
    """A game unit with logic and state, using the GenericGraphicsCreator for display."""
