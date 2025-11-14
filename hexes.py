import dataclasses
from typing import Sequence
from math import cos, sin, pi, sqrt, floor, ceil
from pyodide.ffi import create_proxy
import js

from functools import singledispatchmethod


@dataclasses.dataclass
class Hex:
    i: int
    j: int
    k: int

    def __post_init__(self):
        if self.i + self.j + self.k != 0:
            self.k = -self.i - self.j  # Enforce constraint

    @classmethod
    def hex_distance(cl, a: "Hex", b: "Hex") -> int:
        return (abs(a.i - b.i) + abs(a.j - b.j) + abs(a.k - b.k)) // 2

    
    def neighbor_hex(self, direction: int) -> "Hex":
        directions = [
            Hex(1, -1, 0), Hex(1, 0, -1), Hex(0, 1, -1),
            Hex(-1, 1, 0), Hex(-1, 0, 1), Hex(0, -1, 1)
        ]
        dir = directions[direction % 6]
        return Hex(self.i + dir.i, self.j + dir.j, self.k + dir.k)

    def neighbors(self) -> Sequence["Hex"]:
        return [self.neighbor_hex(direction) for direction in range(6)]
    
    def radius(self, n: int) -> Sequence["Hex"]:
        results = []
        for x in range(-n, n + 1):
            for y in range(max(-n, -x - n), min(n, -x + n) + 1):
                z = -x - y
                results.append(Hex(self.i + x, self.j + y, self.k + z))
        return results
    
    def line_to(self, other: 'Hex') -> Sequence['Hex']:
        N = Hex.hex_distance(self, other)
        results = []
        for i in range(N + 1):
            t = i / max(N, 1)
            lerped = Hex(
                round(self.i + (other.i - self.i) * t),
                round(self.j + (other.j - self.j) * t),
                round(self.k + (other.k - self.k) * t)
            )
            results.append(lerped)
        return results

    def __add__(self, other: 'Hex') -> 'Hex':
        return Hex(self.i + other.i, self.j + other.j, self.k + other.k)

    def __sub__(self, other: 'Hex') -> 'Hex':
        return Hex(self.i - other.i, self.j - other.j, self.k - other.k)

    def __mul__(self, k: int) -> 'Hex':
        return Hex(self.i * k, self.j * k, self.k * k)
    
    def __div__(self, k: int) -> 'Hex':
        return Hex(round(self.i / k), round(self.j / k), round(self.k / k))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Hex):
            return NotImplemented
        return self.i == other.i and self.j == other.j and self.k == other.k

    def __hash__(self) -> int:
        return hash((self.i, self.j, self.k))

    def __repr__(self) -> str:
        return f"Hex(i={self.i}, j={self.j}, k={self.k},{(self.i + self.k + self.j)==0})"

class HexLayout:
    """
    Converts between hex coordinates and pixel coordinates for flat-topped hexagons
    """
    def __init__(self, size: float, origin_x: float = 0.0, origin_y: float = 0.0):
        self.size = size
        self.origin_x = origin_x
        self.origin_y = origin_y

    def hex_to_pixel(self, hex: Hex) -> tuple[float, float]:
        x = self.size * (3/2 * hex.i) + self.origin_x
        y = self.size * ( (3**0.5) * (hex.j + hex.i / 2) ) + self.origin_y
        return (x, y)
    
    def pixel_to_hex(self, x: float, y: float) -> Hex:
        x = (x - self.origin_x) / self.size
        y = (y - self.origin_y) / self.size
        q = (2.0/3 * x )
        r = (-1.0/3 * x + sqrt(3)/3 * y)
        return Hex(round(q), round(r), round(-q - r))
    
    def hex_corners(self, hex: Hex) -> list[tuple[float, float]]:
        center_x, center_y = self.hex_to_pixel(hex)
        corners = []
        for i in range(6):
            angle = 2 * pi * i / 6
            corner_x = center_x + self.size * cos(angle)
            corner_y = center_y + self.size * sin(angle)
            corners.append((corner_x, corner_y))
        return corners
        


class HexCanvas:
    def __init__(self, canvas_id: str, hex_size):
        self.canvas = js.document.getElementById(canvas_id)
        self.context = self.canvas.getContext("2d")
        self.hex_layout = HexLayout(hex_size, self.canvas.width / 2, self.canvas.height / 2)
        self.hex_width = hex_size * 2
        self.hex_height = (3 ** 0.5) * hex_size

    def set_size(self, width: int, height: int):
        self.canvas.width = width
        self.canvas.height = height
        
    def fill_canvas(self, color: str):
        self.context.fillStyle = color
        self.context.fillRect(0, 0, self.canvas.width, self.canvas.height)

    def draw_hex(self, hex: Hex, fill = "white", stroke = "black"):

        points = self.hex_layout.hex_corners(hex)
        points.append(points[0])  # Close the hexagon
        self.context.beginPath()
        self.context.strokeStyle = stroke
        self.context.fillStyle = fill
        for p in points:
            self.context.lineTo(*p)
            self.context.stroke()
        self.context.closePath()
        self.context.fill()


    def draw_text(self, hex: Hex, text: str, font: str = "12px Arial", color: str = "black"):
        x, y = self.hex_layout.hex_to_pixel(hex)
        self.context.fillStyle = color
        self.context.font = font
        self.context.fillText(text, x - self.hex_width / 4, y)

    def on_canvas_click(self, event, context):
        rect = event.target.getBoundingClientRect()
        x = event.clientX - rect.left
        y = event.clientY - rect.top
        hex = self.hex_layout.pixel_to_hex(x, y)
    
        #self.draw_hex_line(Hex(0,0,0), hex)'

        #self.draw_hex_ring(hex, 3)
        self.draw_hex_arc(hex, 3, 0, 2)
            # for h in self.

            # if hex in self:
            #     for h in hex.neighbors():
            #         self.draw_hex(h, fill="#FF000027")
            #     print(f"Clicked at pixel ({x}, {y}), which is in hex {hex}")
            #     self.draw_hex(hex, fill="#00E1FF27")

    @singledispatchmethod
    def __contains__(self, hex: Hex) -> bool:
        for p in self.hex_layout.hex_corners(hex):
            x, y = p
            if not (0 <= x <= self.canvas.width and 0 <= y <= self.canvas.height):
                return False
        return True

    @__contains__.register
    def __contains_pixel__(self, x: float, y: float) -> bool:
        hex = self.hex_layout.pixel_to_hex(x, y)
        return self.__contains__(hex)

    def draw_hex_line(self, a: Hex, b: Hex) -> Sequence[Hex]:
        N = Hex.hex_distance(a, b)
        results = []
        for i in range(N + 1):
            t = i / max(N, 1)
            lerped = Hex(
                round(a.i + (b.i - a.i) * t),
                round(a.j + (b.j - a.j) * t),
                round(a.k + (b.k - a.k) * t)
            )
            results.append(lerped)
        for h in results:
            self.draw_hex(h, fill="#FF000027")


    def draw_hex_ring(self, center: Hex, radius: int) -> Sequence[Hex]:
        results = []
        for x in range(-radius, radius + 1):
            for y in range(max(-radius, -x - radius), min(radius, -x + radius) + 1):
                z = -x - y
                hex = Hex(center.i + x, center.j + y, center.k + z)
                results.append(hex)
        for result in results:
            self.draw_hex(result, fill="#FF000027")

    def draw_hex_arc(self, hex: Hex, radius: int, start_angle: int, end_angle: int) -> Sequence[Hex]:
        results = []
        for angle in range(start_angle, end_angle + 1):
            direction = angle % 6
            hex = hex
            for _ in range(radius):
                hex = hex.neighbor_hex(direction)
            results.append(hex)
        for result in results:
            self.draw_hex(result, fill="#FF000027")

def main():


    hex_canvas = HexCanvas("hexCanvas", 24)
    hex_canvas.fill_canvas("lightgrey")

    for x in range(-19, 20):
        for y in range(-19, 20):
            z = -x - y
            hex = Hex(x, y, z)
            if hex in hex_canvas:
                fill_color = "#7a9eb5"
                hex_canvas.draw_hex(hex, fill=fill_color, stroke="black")
                hex_canvas.draw_text(hex, f"{hex.i},{hex.j},{hex.k}", font="10px Arial", color="blue")
   
    hex_canvas.canvas.mouseclick = create_proxy(lambda event: hex_canvas.on_canvas_click(event, hex_canvas.context))
    hex_canvas.canvas.addEventListener("click", hex_canvas.canvas.mouseclick)

if __name__ == "__main__":
    main()
