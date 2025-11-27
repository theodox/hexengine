
import dataclasses

@dataclasses.dataclass(frozen=True)
class Cartesian:
    x: float
    y: float

@dataclasses.dataclass(frozen=True)
class CartesianInt:
    x: int
    y: int

    def __eq__(self, value):
        if not isinstance(value, CartesianInt):
            return NotImplemented
        return self.x == value.x and self.y == value.y
    
    def __hash__(self) -> int:
        return hash((self.x - 4096, self.y - 2048))
    
    def __repr__(self) -> str:
        return f"CartesianInt({self.x},{self.y})"
    
    def __add__(self, other: "CartesianInt") -> "CartesianInt":
        return CartesianInt(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other: "CartesianInt") -> "CartesianInt":
        return CartesianInt(self.x - other.x, self.y - other.y)
    
    def __mul__(self, k: int) -> "CartesianInt":
        return CartesianInt(self.x * k, self.y * k) 
    
    def __truediv__(self, k: int) -> "CartesianInt":
        return CartesianInt(self.x // k, self.y // k)
    

        
@dataclasses.dataclass(frozen=True)
class Hex:
    i: int
    j: int
    k: int

    def __post_init__(self):
        # force these to be integers and enforce the constraint i + j + k = 0
        # but make the hex immutable
        object.__setattr__(self, 'i', round(self.i))
        object.__setattr__(self, 'j', round(self.j))
        object.__setattr__(self, 'k', round(self.k))
        if self.i + self.j + self.k != 0:
            object.__setattr__(self, 'k', -self.i - self.j)  # Enforce constraint

    def __add__(self, other: "Hex") -> "Hex":
        return Hex(self.i + other.i, self.j + other.j, self.k + other.k)

    def __iadd__(self, other: "Hex") -> "Hex":
        raise NotImplementedError("In-place addition is not supported for Hex")

    def __sub__(self, other: "Hex") -> "Hex":
        return Hex(self.i - other.i, self.j - other.j, self.k - other.k)

    def __isub__(self, other: "Hex") -> "Hex":
        raise NotImplementedError("In-place subtraction is not supported for Hex")

    def __mul__(self, k: float) -> "Hex":
        k *= 1.0
        return Hex(self.i * k, self.j * k, self.k * k)

    def __imul__(self, k: float) -> "Hex":
        raise NotImplementedError("In-place multiplication is not supported for Hex")

    def __truediv__(self, k: float) -> "Hex":
        k *= 1.0
        return Hex(self.i / k, self.j / k, self.k / k)
    
    def __floordiv__(self, k: float) -> "Hex":
        k *= 1.0
        return Hex(self.i // k, self.j // k, self.k // k)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Hex):
            return NotImplemented
        return self.i == other.i and self.j == other.j and self.k == other.k

    def __len__(self) -> int:
        return max(abs(self.i), abs(self.j), abs(self.k))

    def __repr__(self) -> str:
        return f"Hex({self.i},{self.j},{self.k})"
    
    def __hash__(self) -> int:
        return hash((self.i + 1024, self.j + 2048, self.k + 4096))