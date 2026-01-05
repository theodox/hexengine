from typing import Iterable, TYPE_CHECKING

from ..document import js
from ..hexes.types import Hex
from ..map.layout import HexLayout

if TYPE_CHECKING:
    from ..game.game import Game


class Location:
    def __init__(
        self, hex: Hex, terrain_type: str, movement_cost: float, game: "Game"
    ) -> None:
        self._hex = hex
        self._type = terrain_type
        self._cost = movement_cost
        self._display = DisplayLocation(hex, self._type, game.canvas.hex_layout)
        self._display.create_graphics(game.canvas.svg_layer._svg)

    @property
    def position(self) -> Hex:
        return self._hex

    @property
    def loc_type(self) -> str:
        return self._type

    @property
    def movement_cost(self) -> float:
        return self._cost

    @classmethod
    def create(cls, loc_item, game: "Game" = None) -> "Location":
        pos = loc_item.position
        terrain = loc_item.type
        movement_cost = loc_item.movement_cost
        return cls(pos, terrain, movement_cost, game)

    def __repr__(self) -> str:
        return f"<{self._hex.i},{self._hex.j},{self._hex.k} = {self.loc_type}>"


class DisplayLocation:
    """The display component of a location on the board."""
    SVG = "http://www.w3.org/2000/svg"

    def __init__(self, hex: Hex, loc_type: str, layout: HexLayout = None) -> None:
        self.loc_type = loc_type
        self._hex = hex
        self._hex_layout = layout
        self.proxy = None

    def create_graphics(self, svg_layer) -> None:
        # Example graphics creation for a location
        points = []
        for point in self._hex_layout.hex_corners(self._hex):
            points.append(f"{point[0]},{point[1]}")

        polygon = js.document.createElementNS(self.SVG, "polygon")
        polygon.setAttribute("points", " ".join(points))
        polygon.classList.add("location")
        polygon.classList.add(self.loc_type)
        svg_layer.appendChild(polygon)
        self.proxy = polygon

    def push_classes(self, *classes: Iterable[str]) -> None:
        for cl in classes:
            self.proxy.classList.add(cl)
