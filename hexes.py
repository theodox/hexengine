import dataclasses
import time
from typing import Sequence, Iterable
from math import atan2, copysign, cos, sin, pi, sqrt, ceil, floor
from pyodide.ffi import create_proxy
import js

from functools import singledispatchmethod

TWO_PI = 2 * pi
PI_OVER_3 = pi / 3.0
PI_OVER_6 = pi / 6.0

@dataclasses.dataclass
class Hex:
    i: int
    j: int
    k: int

    def __post_init__(self):
        self.i = round(self.i)
        self.j = round(self.j)
        self.k = round(self.k)
        if self.i + self.j + self.k != 0:
            self.k = -self.i - self.j  # Enforce constraint

    def __add__(self, other: 'Hex') -> 'Hex':
        return Hex(self.i + other.i, self.j + other.j, self.k + other.k)
    
    def __iadd__(self, other: 'Hex') -> 'Hex':
        self.i += other.i
        self.j += other.j
        self.k += other.k
        return self

    def __sub__(self, other: 'Hex') -> 'Hex':
        return Hex(self.i - other.i, self.j - other.j, self.k - other.k)

    def __isub__(self, other: 'Hex') -> 'Hex':
        self.i -= other.i
        self.j -= other.j
        self.k -= other.k
        return self

    def __mul__(self, k: float) -> 'Hex':
        k *= 1.0
        return Hex(self.i * k, self.j * k, self.k * k)
    
    def __imul__(self, k: float) -> 'Hex':
        self.i *= k
        self.j *= k
        self.k *= k
        return self

    def __div__(self, k: float) -> 'Hex':
        k *= 1.0
        return Hex(self.i / k, self.j / k, self.k /  k)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Hex):
            return NotImplemented
        return self.i == other.i and self.j == other.j and self.k == other.k

    def __hash__(self) -> int:
        return hash((self.i + 1024, self.j + 2048, self.k + 4096))

    def __len__(self) -> int:
        return max(abs(self.i), abs(self.j), abs(self.k))
    
    def __repr__(self) -> str:
        return f"Hex({self.i},{self.j},{self.k})"
    

def cube_round(coords):
    q = round(coords[0])
    r = round(coords[1])
    s = round(coords[2])

    q_diff = abs(q - coords[0])
    r_diff = abs(r - coords[1])
    s_diff = abs(s - coords[2])

    if q_diff > r_diff and q_diff > s_diff:
        q = -r-s
    elif r_diff > s_diff:
        r = -q-s
    else:
        s = -q-r
    return Hex(q, r, s)

def normalize(hex: Hex) -> Hex:
    
    i = (hex.i + 0.24999) / len(hex)
    j = (hex.j - 0.24999) / len(hex)
    k = -i - j
    return Hex(round(i), round(j), round(k))

def neighbors(hex: Hex) -> Iterable[Hex]:
    for h in radial(hex, 1):
        if h != hex:    
            yield h

def neighbor_hex(hex: Hex, direction: int) -> Hex:
    return tuple(neighbors(hex))[direction % 6]

def distance(a: Hex, b: Hex) -> int:
    return (abs(a.i - b.i) + abs(a.j - b.j) + abs(a.k - b.k)) // 2

def lerp(a: Hex, b: Hex, t: float) ->  Hex:
    """
    lerp the hexes with a small nudge to avoid rounding issues
    """
    i = a.i + (b.i - a.i) * t
    j =  a.j + (b.j - a.j) * t
    k = a.k + (b.k - a.k) * t

    return cube_round((i, j, k))

    # i += copysign( .001, i)
    # j -= copysign( .001, i)
    # return Hex(i , j, k)


def line(a: Hex, b: Hex) -> Iterable[Hex]:
    N = distance(a, b)
   
    for i in range(N + 1):
        t = i / max(N, 1)
        next_hex = lerp(a, b, t)
        yield next_hex

def path(steps: Sequence[Hex]) -> Iterable[Hex]:
    if len(steps) < 2:
        return
    for idx in range(len(steps) - 1):
        a = steps[idx]
        b = steps[idx + 1]
        for h in line(a, b):
            yield h


def radial(center: Hex, radius: int) -> Iterable[Hex]:
    for x in range(-radius, radius + 1):
        for y in range(max(-radius, -x - radius), min(radius, -x + radius) + 1):
            z = -x - y
            yield Hex(center.i + x, center.j + y, center.k + z)

def ring(center: Hex, radius: int) -> Iterable[Hex]:
    for r in radial(center, radius):
        if distance(center, r) == radius:
            yield r

def wedge(center: Hex, radius: int, direction: int) -> Iterable[Hex]:
    for r in radial(center, radius):
        dir_hex = neighbor_hex(center, direction)
        if distance(center, r) == radius and distance(center, r + dir_hex) < radius:
            yield r

def angle(start: Hex, end: Hex) -> float:
    delta = end - start
    angle = PI_OVER_6  # 30 degrees for flat-topped hexes
    x = delta.i * cos(angle) + delta.j * cos(angle + 2 * PI_OVER_3) + delta.k * cos(angle + 4 * PI_OVER_3)
    y = delta.i * sin(angle) + delta.j * sin(angle + 2 * PI_OVER_3) + delta.k * sin(angle + 4 * PI_OVER_3)
    return (PI_OVER_3 + atan2(y, x) +  TWO_PI) % TWO_PI


def wedge_fill(center: Hex, radius: int, start_angle: float, end_angle: float) -> Iterable[Hex]:
    # 0.05 is 3 degrees of leeway to make sure we dont miss the 0 line
    for rad in radial(center, radius):
        ang = angle(center, rad)
        if start_angle - 0.06 <= ang  <= end_angle or rad==center:
            yield rad

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
    
        for h in line(Hex(0,0,0), hex):
            self.draw_hex(h, fill="#FF000027")


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
    def draw_hex_arc(self, center: Hex, radius: int, start_angle: int, end_angle: int) -> Sequence[Hex]:
        results = wedge(center, radius, start_angle)
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

    t = time.time()
    for r in wedge_fill(Hex(0,0,0), 8, 0, 2* pi / 3):
        hex_canvas.draw_hex(r, fill="#FF000027")    
    print ("wedge_fill time:", (time.time() - t) * 1000.0, "ms")

    print(angle(Hex(0,0,0), Hex(0,-9,9)))

if __name__ == "__main__":
    main()
