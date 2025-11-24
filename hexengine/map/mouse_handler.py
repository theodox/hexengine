import js  # pyright: ignore[reportMissingImports]
import logging
from ..hexes import shapes
from .canvas import Map


class MouseHandler:
    def __init__(self, canvas: Map):
        self.canvas = canvas
        self.logger = logging.getLogger("MouseHandler")
        self.last_click_time = 0
        self.last_click_pos = -1000, -1000
        self.start = None
        self.end = None


    def reset(self):
        self.start = None
        self.end = None
        self.last_click_time = 0
        self.last_click_pos = -1000, -1000

    def on_click(self, event, ctx):
        if js.Date.now() - self.last_click_time < 300:
            return  # ignore click if too close to last mouse up (handled as dblclick)
        self.logger.warning("clicked")
        self.reset()

    def on_dblclick(self, event, ctx):
        self.logger.warning("double clicked")

    def on_drag(self, event, ctx):
        self.logger.warning("dragging")

    def on_mouse_down(self, event, ctx):
        self.start = self.canvas.get_click_coords(event)
        self.logger.warning("mouse down")

    def on_mouse_up(self, event, ctx):
        self.end = self.canvas.get_click_coords(event)
        line = shapes.line(
            self.canvas._hex_layout.pixel_to_hex(*self.start),
            self.canvas._hex_layout.pixel_to_hex(*self.end),
        )   
        if self.start == self.end:
            self.logger.warning("mouse up with no movement")
            self.reset()
            return
        for h in line:
            self.canvas.draw_hex(h, fill="#0000FF27")
            self.last_click_pos = self.end
            self.last_click_time = js.Date.now()

        self.logger.warning("mouse up")
