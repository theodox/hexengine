import dataclasses

# Constants for hex to cartesian conversion
SQRT_THREE = 3**0.5
THREE_HALF_POWER = SQRT_THREE / 2


@dataclasses.dataclass(frozen=True)
class Cartesian:
    x: int
    y: int

    def __post_init__(self):
        # force these to be integers
        object.__setattr__(self, "x", round(self.x))
        object.__setattr__(self, "y", round(self.y))

    def __eq__(self, value):
        if not isinstance(value, Cartesian):
            return NotImplemented
        return self.x == value.x and self.y == value.y

    def __hash__(self) -> int:
        return hash((self.x - 4096, self.y - 2048))

    def __repr__(self) -> str:
        return f"Cartesian({self.x},{self.y})"

    def __add__(self, other: "Cartesian") -> "Cartesian":
        return Cartesian(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Cartesian") -> "Cartesian":
        return Cartesian(self.x - other.x, self.y - other.y)

    def __mul__(self, k: int) -> "Cartesian":
        return Cartesian(self.x * k, self.y * k)

    def __truediv__(self, k: int) -> "Cartesian":
        return Cartesian(self.x // k, self.y // k)

    @classmethod
    def from_hex(cls, hex_coord: "Hex") -> "Cartesian":
        """Convert hex coordinates to integer Cartesian coordinates (flat-top orientation)."""
        x = int(round(1.5 * hex_coord.i))
        y = int(round(SQRT_THREE * (hex_coord.j + hex_coord.i * 0.5)))
        return cls(x, y)


@dataclasses.dataclass(frozen=True)
class HexRowCol:
    """
    Hex-aligned row/column coordinates for flat-topped hexes.
    
    This provides a 1:1 mapping with Hex coordinates:
    - row: the hex row (j coordinate)
    - col: the hex column position (i coordinate)
    
    Unlike Cartesian coordinates, each HexRowCol maps to exactly one Hex
    and vice versa.
    """
    row: int
    col: int

    def __post_init__(self):
        object.__setattr__(self, "row", round(self.row))
        object.__setattr__(self, "col", round(self.col))

    def __eq__(self, value):
        if not isinstance(value, HexRowCol):
            return NotImplemented
        return self.row == value.row and self.col == value.col

    def __hash__(self) -> int:
        return hash((self.row, self.col))

    def __repr__(self) -> str:
        return f"HexRowCol(row={self.row}, col={self.col})"

    def __add__(self, other: "HexRowCol") -> "HexRowCol":
        return HexRowCol(self.row + other.row, self.col + other.col)

    def __sub__(self, other: "HexRowCol") -> "HexRowCol":
        return HexRowCol(self.row - other.row, self.col - other.col)

    @classmethod
    def from_hex(cls, hex_coord: "Hex") -> "HexRowCol":
        """Convert hex coordinates to row/col coordinates (1:1 mapping)."""
        return cls(row=hex_coord.j, col=hex_coord.i)

    def to_hex(self) -> "Hex":
        """Convert row/col coordinates to hex coordinates (1:1 mapping)."""
        i = self.col
        j = self.row
        k = -i - j
        return Hex(i, j, k)


@dataclasses.dataclass(frozen=True)
class Hex:
    i: int
    j: int
    k: int

    def __post_init__(self):
        # force these to be integers and enforce the constraint i + j + k = 0
        # but make the hex immutable
        object.__setattr__(self, "i", round(self.i))
        object.__setattr__(self, "j", round(self.j))
        object.__setattr__(self, "k", round(self.k))
        if self.i + self.j + self.k != 0:
            object.__setattr__(self, "k", -self.i - self.j)  # Enforce constraint

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

    @classmethod
    def from_cartesian(cls, cartesian: Cartesian) -> "Hex":
        """Convert integer Cartesian coordinates to hex coordinates (flat-top orientation)."""
        i = (2.0 / 3.0) * cartesian.x
        j = cartesian.y / SQRT_THREE - i * 0.5
        k = -i - j

        q = round(i)
        r = round(j)
        s = round(k)

        q_diff = abs(q - i)
        r_diff = abs(r - j)
        s_diff = abs(s - k)

        if q_diff > r_diff and q_diff > s_diff:
            q = -r - s
        elif r_diff > s_diff:
            r = -q - s
        else:
            s = -q - r
        return cls(q, r, s)
