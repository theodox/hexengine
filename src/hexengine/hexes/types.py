from __future__ import annotations

import dataclasses

from .constants import (
    FLAT_TOP_AXIAL_TO_PLANE_X,
    FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE,
    SQRT_THREE,
)


@dataclasses.dataclass(frozen=True)
class Cartesian:
    """
    Integer point on the **flat-top hex embedding plane** (skewed 2D lattice).

    Each `Hex` maps to a canonical `(x, y)` via `from_hex` using the
    same scale factors as continuous hex layout (see `hexengine.hexes.constants`).
    The reverse map `Hex.from_cartesian` rounds to the nearest hex, so **several**
    distinct `Cartesian` values can yield the **same** `Hex`—unlike
    `HexColRow` (odd-q), which is 1:1 with hexes.

    Useful for axis-aligned ranges and plane geometry (e.g. `hexengine.hexes.shapes`);
    it is **not** the same as odd-q `[col, row]` editor coordinates.
    """

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

    def __add__(self, other: Cartesian) -> Cartesian:
        return Cartesian(self.x + other.x, self.y + other.y)

    def __sub__(self, other: Cartesian) -> Cartesian:
        return Cartesian(self.x - other.x, self.y - other.y)

    def __mul__(self, k: int) -> Cartesian:
        return Cartesian(self.x * k, self.y * k)

    def __truediv__(self, k: int) -> Cartesian:
        return Cartesian(self.x // k, self.y // k)

    @classmethod
    def from_hex(cls, hex_coord: Hex) -> Cartesian:
        """Convert hex coordinates to integer Cartesian coordinates (flat-top orientation)."""
        x = int(round(FLAT_TOP_AXIAL_TO_PLANE_X * hex_coord.i))
        y = int(round(SQRT_THREE * (hex_coord.j + hex_coord.i * 0.5)))
        return cls(x, y)


@dataclasses.dataclass(frozen=True)
class HexColRow:
    """
    **Odd-q offset** coordinates for a flat-top hex grid (human-friendly 2-number layout).

    - `col` — column index; matches axial `i` and typical editor `data-x` / Hextml.
    - `row` — **offset row**, not axial `j`. Neighboring hexes do not simply increment
      `row`; stagger follows the odd-q rule (Red Blob Games: offset coordinates).

    Use `axial_from_offset` and `offset_from_axial` for the odd-q ↔ axial
    formulas (Red Blob Games: offset coordinates → axial). Scenario TOML
    `position = [col, row]` uses the same two numbers.

    Bijective with `Hex` (cube / axial) for integer grids; use `to_hex` /
    `from_hex` to convert. This is **not** the same as integer `Cartesian`
    plane coordinates.
    """

    col: int
    row: int

    @classmethod
    def axial_from_offset(cls, col: int, row: int) -> tuple[int, int]:
        """
        Odd-q offset `(col, row)` → axial `(i, j)`.

        `col` equals axial `i` (e.g. Hextml `data-x`); `row` is the staggered
        offset index (e.g. `data-y`), not axial `j`.
        """
        i = int(col)
        j = int(row) - (i - (i & 1)) // 2
        return i, j

    @classmethod
    def offset_from_axial(cls, i: int, j: int) -> HexColRow:
        """
        Axial `(i, j)` → odd-q coordinates with `col = i`.

        `row` is the offset-row index: `j + (i - (i & 1)) // 2` (inverse of
        `axial_from_offset` for the row component).
        """
        ii = int(i)
        row = int(j) + (ii - (ii & 1)) // 2
        return cls(col=ii, row=row)

    def __post_init__(self):
        object.__setattr__(self, "col", round(self.col))
        object.__setattr__(self, "row", round(self.row))

    def __eq__(self, value):
        if not isinstance(value, HexColRow):
            return NotImplemented
        return self.col == value.col and self.row == value.row

    def __hash__(self) -> int:
        return hash((self.col, self.row))

    def __repr__(self) -> str:
        return f"HexColRow(col={self.col}, row={self.row})"

    @classmethod
    def from_hex(cls, hex_coord: Hex) -> HexColRow:
        """Axial/cube hex → odd-q `(col, row)` with `col = i`."""
        return cls.offset_from_axial(hex_coord.i, hex_coord.j)

    def to_hex(self) -> Hex:
        """Odd-q `(col, row)` → cube hex (`k = -i - j`)."""
        i, j = self.__class__.axial_from_offset(self.col, self.row)
        return Hex(i, j, -i - j)


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

    def __add__(self, other: Hex) -> Hex:
        return Hex(self.i + other.i, self.j + other.j, self.k + other.k)

    def __iadd__(self, other: Hex) -> Hex:
        raise NotImplementedError("In-place addition is not supported for Hex")

    def __sub__(self, other: Hex) -> Hex:
        return Hex(self.i - other.i, self.j - other.j, self.k - other.k)

    def __isub__(self, other: Hex) -> Hex:
        raise NotImplementedError("In-place subtraction is not supported for Hex")

    def __mul__(self, k: float) -> Hex:
        k *= 1.0
        return Hex(self.i * k, self.j * k, self.k * k)

    def __imul__(self, k: float) -> Hex:
        raise NotImplementedError("In-place multiplication is not supported for Hex")

    def __truediv__(self, k: float) -> Hex:
        k *= 1.0
        return Hex(self.i / k, self.j / k, self.k / k)

    def __floordiv__(self, k: float) -> Hex:
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
    def from_cartesian(cls, cartesian: Cartesian) -> Hex:
        """Convert integer Cartesian coordinates to hex coordinates (flat-top orientation)."""
        i = FLAT_TOP_PLANE_TO_AXIAL_Q_SCALE * cartesian.x
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

    @classmethod
    def from_hex_col_row(cls, col_row: HexColRow) -> Hex:
        """Odd-q `HexColRow` → cube hex (inverse of `HexColRow.from_hex`)."""
        return col_row.to_hex()
