import logging
from .map import Map
from .document import element
from .hexes.types import Hex

class Game:
    def __init__(self):
        self.running = True
        container = element("map-container")
        map = element("map-canvas")
        svg = element("map-svg")
        units = element("map-units")
        assert map is not None, "Map canvas element not found"
        assert svg is not None, "Map SVG element not found"
        self.canvas = Map(container, map, svg, units)

        self.logger = logging.getLogger("game")
        self.logger.info("Game initialized")

        self.canvas.on_click < self.on_click
        
       
        # Add a test unit
        for r in range(10):
            u = self.canvas.add_unit(f"unit{r}", "soldier")
            u.position = Hex(0, r,-r)
            u.visible = True

       
    def on_click(self, *args):
        logging.getLogger("map").info(f">{args[0].target.id}< clicked")
        unit_id = args[0].target.getAttribute("data-unit")
        if unit_id:
            unit = self.canvas.units.get_unit(unit_id)
            unit.active = not unit.active
            logging.getLogger("game").info(f"Unit {unit.unit_id} active state is now {unit.active}")
        else:
            h = self.canvas.hex_layout.pixel_to_hex(args[0].offsetX, args[0].offsetY)
            for u in self.canvas.units.get_units():
                if u.active: 
                    logging.getLogger("game").info(f"Moving active unit {u.unit_id} to hex ({h.i},{h.j},{h.k})")
                    u.position = h
                    u.active = False