import dataclasses
from typing import Sequence
from math import cos, sin
from pyodide.ffi import create_proxy
import js

@dataclasses.dataclass
class Hex:
    i: int
    j: int
    k: int

def __post_init__(self):
    if self.i + self.j + self.k != 0:
        raise ValueError("Invalid hex coordinates: i + j + k must equal 0")

def hex_distance(a: Hex, b: Hex) -> int:
    return (abs(a.i - b.i) + abs(a.j - b.j) + abs(a.k - b.k)) // 2

def neighbor_hex(hex: Hex, direction: int) -> Hex:
    directions = [
        Hex(1, -1, 0), Hex(1, 0, -1), Hex(0, 1, -1),
        Hex(-1, 1, 0), Hex(-1, 0, 1), Hex(0, -1, 1)
    ]
    dir = directions[direction % 6]
    return Hex(hex.i + dir.i, hex.j + dir.j, hex.k + dir.k)

def neighbors(hex: Hex) -> Sequence[Hex]:
    return [neighbor_hex(hex, direction) for direction in range(6)] 

def __add__(self, other: 'Hex') -> 'Hex':
    return Hex(self.i + other.i, self.j + other.j, self.k + other.k)

def __sub__(self, other: 'Hex') -> 'Hex':
    return Hex(self.i - other.i, self.j - other.j, self.k - other.k)

def __mul__(self, k: int) -> 'Hex':
    return Hex(self.i * k, self.j * k, self.k * k)

def __eq__(self, other: object) -> bool:
    if not isinstance(other, Hex):
        return NotImplemented
    return self.i == other.i and self.j == other.j and self.k == other.k

def __hash__(self) -> int:
    return hash((self.i, self.j, self.k))


class HexLayout:
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
        q = (2/3 * x)
        r = (-1/3 * x + (3**0.5)/3 * y)
        return Hex(round(q), round(r), round(-q - r))
    
    def hex_corners(self, hex: Hex) -> list[tuple[float, float]]:
        center_x, center_y = self.hex_to_pixel(hex)
        corners = []
        for i in range(6):
            angle = 2 * 3.141592653589793 * i / 6
            corner_x = center_x + self.size * cos(angle)
            corner_y = center_y + self.size * sin(angle)
            corners.append((corner_x, corner_y))
        return corners
    
    def draw_hex(self, context, hex: Hex, fill = "white", stroke = "black"):
        corners = self.hex_corners(hex)
        context.beginPath()
        points = HexLayout(25).hex_corners(hex)
        points.append(points[0])  # Close the hexagon
        context.beginPath()
        context.strokeStyle = stroke
        context.stroke()
        context.fillStyle = fill
        for p in points:
            context.lineTo(p[0] + 400, p[1] + 400)
            context.stroke()
        context.closePath()
        context.fill()
        print("Drew hex at", hex)

def on_canvas_click(event, context):
    rect = event.target.getBoundingClientRect()
    x = event.clientX - rect.left
    y = event.clientY - rect.top
    hex = HexLayout(25).pixel_to_hex(x - 400, y - 400)
    print(f"Clicked at pixel ({x}, {y}), which is in hex {hex}")
    canvas = js.document.getElementById("hexCanvas")
    context = canvas.getContext("2d")
    HexLayout(25).draw_hex(context, hex, fill="#FFFF0027", stroke="red")


def main():

    canvas = js.document.getElementById("hexCanvas")
    context = canvas.getContext("2d")
    context.fillStyle = "#D3D3D3"
    context.fillRect(0, 0, canvas.width, canvas.height)
    context.strokeStyle = "#043704"
    for x in range(-8, 9):
        for y in range(-8, 9):
            z = -x - y
            if abs(z) <= 8:
                hex = Hex(x, y, z)
                #print(f"Hex: {hex}, Pixel: {HexLayout(10).hex_to_pixel(hex)}")
                points = HexLayout(25).hex_corners(hex)
                points.append(points[0])  # Close the hexagon
                context.beginPath()
                for p in points:
                    context.lineTo(p[0] + 400, p[1] + 400)
                    context.stroke()
                context.closePath()
                r = int((x + 8) / 16 * 255)
                g = int((y + 8) / 16 * 255)
                b = int((z + 8) / 16 * 255)
                color = f"rgb({r},{g},{b})"
                context.fillStyle = color
                context.fill()
                
    for x in range(-8, 9):
        for y in range(-8, 9):
            z = -x - y
            if abs(z) <= 8:      
                hex = Hex(x, y, z)     
                context.fillStyle = "#000000"
                xx, yy = HexLayout(25).hex_to_pixel(hex)
                context.font = "10px Arial"
                context.fillText(f"{hex.i}, {hex.j}, {hex.k}", xx + 385, yy + 404)
                
    context.mouseclick = create_proxy(lambda event: on_canvas_click(event, context))
    context.canvas.addEventListener("click", context.mouseclick)

if __name__ == "__main__":
    main()
