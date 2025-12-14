from typing import TYPE_CHECKING

from ..hexes.types import Hex
from .graphics import DisplayUnit, GraphicsCreator

if TYPE_CHECKING:
    from ..map import Map


class GameUnit:
    """A game unit with logic and state."""

    GRAPHICS_CREATOR: GraphicsCreator = None

    def __init__(self, unit_id: str, unit_type: str, unit_display: DisplayUnit):
        self.unit_id = unit_id
        self.unit_type = unit_type
        self.display = unit_display
        self.health = 100  # Default health

    def move_to(self, hex: Hex):
        self.display.position = hex

    def _set_visible(self, value: bool):
        self.display.visible = value

    def _get_visible(self) -> bool:
        return self.display.visible

    def _set_position(self, hex: Hex):
        self.display.position = hex

    def _get_position(self) -> Hex:
        return self.display.position

    def _get_rotation(self) -> float:
        return self.display.rotation

    def _set_rotation(self, angle: float):
        self.display.rotation = angle

    def _get_active(self) -> bool:
        return self.display.active

    def _set_active(self, value: bool):
        self.display.active = value

    visible = property(_get_visible, _set_visible)
    position = property(_get_position, _set_position)
    rotation = property(_get_rotation, _set_rotation)
    active = property(_get_active, _set_active)

    def __repr__(self):
        return f"<GameUnit id={self.unit_id} type={self.unit_type} at=({self.display.position.i},{self.display.position.j},{self.display.position.k})>"

    def __hash__(self):
        return hash(hash(self.unit_id) ^ hash(self.unit_type))

    @classmethod
    def create(cls, unit_id: str, unit_type: str, map: "Map"):
        display_unit = DisplayUnit(unit_id, unit_type, map.hex_layout)
        graphics = cls.GRAPHICS_CREATOR().create(display_unit)
        return cls(unit_id, unit_type, graphics)
