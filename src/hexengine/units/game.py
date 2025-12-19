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
        self.active = True  # Is the unit active in the game
        self.hilited = False  # Is the unit highlighted


    def _set_active(self, value: bool):
        self._active = value
        self.display.visible = value

    def _get_active(self) -> bool:
        return self._active

    def _set_hilited(self, value: bool):
        self._hilited = value
        self.display.hilited = value

    def _get_hilited(self) -> bool:
        return self._hilited

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

    def _get_hilited(self) -> bool:
        return self.display.hilited

    def _set_hilited(self, value: bool):
        self.display.hilited = value

    def _set_enabled(self, value: bool):
        self.display.enabled = value   

    def _get_enabled(self) -> bool:
        return self.display.enabled
    
    active = property(_get_active, _set_active)
    enabled = property(_get_enabled, _set_enabled)
    visible = property(_get_visible, _set_visible)
    position = property(_get_position, _set_position)
    rotation = property(_get_rotation, _set_rotation)
    hilited = property(_get_hilited, _set_hilited)

    def __repr__(self):
        return f"<GameUnit id={self.unit_id} type={self.unit_type} at=({self.display.position.i},{self.display.position.j},{self.display.position.k})>"

    def __hash__(self):
        return hash(hash(self.unit_id) ^ hash(self.unit_type))
    
    def __bool__(self):
        return self.active

    @classmethod
    def create(cls, unit_id: str, unit_type: str, game_map: "Map") -> "GameUnit":
        display_unit = DisplayUnit(unit_id, unit_type, game_map.hex_layout)
        graphics = cls.GRAPHICS_CREATOR().create(display_unit)
        return cls(unit_id, unit_type, graphics)
