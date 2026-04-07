from __future__ import annotations

import dataclasses
import unittest

from hexengine.hexes.types import Hex


class TestHex(unittest.TestCase):
    """Test cases for the Hex class."""

    def test_hex_creation_valid(self):
        """Test creating a valid hex with i + j + k = 0."""
        hex_coord = Hex(1, -2, 1)
        self.assertEqual(hex_coord.i, 1)
        self.assertEqual(hex_coord.j, -2)
        self.assertEqual(hex_coord.k, 1)

    def test_hex_creation_invalid_constraint_enforced(self):
        """Test that the constraint i + j + k = 0 is enforced by adjusting k."""
        hex_coord = Hex(1, 1, 1)  # Sum = 3, should adjust k to -2
        self.assertEqual(hex_coord.i, 1)
        self.assertEqual(hex_coord.j, 1)
        self.assertEqual(hex_coord.k, -2)  # k adjusted to enforce constraint

    def test_hex_creation_with_floats(self):
        """Test that float inputs are rounded to integers."""
        hex_coord = Hex(1.6, -2.3, 0.7)
        self.assertEqual(hex_coord.i, 2)  # 1.6 rounded to 2
        self.assertEqual(hex_coord.j, -2)  # -2.3 rounded to -2
        self.assertEqual(
            hex_coord.k, 0
        )  # Constraint enforced: -2 - 2 = -4, but 0.7 rounded to 1, then adjusted

    def test_hex_creation_zero_coordinates(self):
        """Test creating hex with zero coordinates."""
        hex_coord = Hex(0, 0, 0)
        self.assertEqual(hex_coord.i, 0)
        self.assertEqual(hex_coord.j, 0)
        self.assertEqual(hex_coord.k, 0)

    def test_hex_immutability(self):
        """Test that Hex objects are immutable (frozen dataclass)."""
        hex_coord = Hex(1, -1, 0)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            hex_coord.i = 2

    def test_hex_addition(self):
        """Test addition of two Hex objects."""
        hex1 = Hex(1, -2, 1)
        hex2 = Hex(0, 1, -1)
        result = hex1 + hex2
        self.assertEqual(result.i, 1)
        self.assertEqual(result.j, -1)
        self.assertEqual(result.k, 0)

    def test_hex_addition_constraint_maintained(self):
        """Test that addition result maintains the constraint."""
        hex1 = Hex(2, -1, -1)
        hex2 = Hex(1, 0, -1)
        result = hex1 + hex2
        self.assertEqual(result.i + result.j + result.k, 0)

    def test_hex_iadd_not_implemented(self):
        """Test that in-place addition raises NotImplementedError."""
        hex1 = Hex(1, -1, 0)
        hex2 = Hex(0, 1, -1)
        with self.assertRaises(NotImplementedError):
            hex1 += hex2

    def test_hex_subtraction(self):
        """Test subtraction of two Hex objects."""
        hex1 = Hex(2, -1, -1)
        hex2 = Hex(1, 0, -1)
        result = hex1 - hex2
        self.assertEqual(result.i, 1)
        self.assertEqual(result.j, -1)
        self.assertEqual(result.k, 0)

    def test_hex_subtraction_constraint_maintained(self):
        """Test that subtraction result maintains the constraint."""
        hex1 = Hex(3, -2, -1)
        hex2 = Hex(1, -1, 0)
        result = hex1 - hex2
        self.assertEqual(result.i + result.j + result.k, 0)

    def test_hex_isub_not_implemented(self):
        """Test that in-place subtraction raises NotImplementedError."""
        hex1 = Hex(2, -1, -1)
        hex2 = Hex(1, 0, -1)
        with self.assertRaises(NotImplementedError):
            hex1 -= hex2

    def test_hex_multiplication_by_scalar(self):
        """Test multiplication of Hex by a scalar."""
        hex_coord = Hex(2, -1, -1)
        result = hex_coord * 2
        self.assertEqual(result.i, 4)
        self.assertEqual(result.j, -2)
        self.assertEqual(result.k, -2)

    def test_hex_multiplication_by_float(self):
        """Test multiplication of Hex by a float scalar."""
        hex_coord = Hex(1, -1, 0)
        result = hex_coord * 2.5
        # Note: The result will be rounded to integers due to __post_init__
        # and constraint will be enforced
        self.assertIsInstance(result.i, int)
        self.assertIsInstance(result.j, int)
        self.assertIsInstance(result.k, int)
        self.assertEqual(result.i + result.j + result.k, 0)

    def test_hex_imul_not_implemented(self):
        """Test that in-place multiplication raises NotImplementedError."""
        hex_coord = Hex(1, -1, 0)
        with self.assertRaises(NotImplementedError):
            hex_coord *= 2

    def test_hex_division_by_scalar(self):
        """Test division of Hex by a scalar."""
        hex_coord = Hex(4, -2, -2)
        result = hex_coord / 2
        # Note: The result will be rounded to integers due to __post_init__
        # and constraint will be enforced
        self.assertEqual(result.i, 2)
        self.assertEqual(result.j, -1)
        self.assertEqual(result.k, -1)
        self.assertEqual(result.i + result.j + result.k, 0)

    def test_hex_floor_division_by_scalar(self):
        """Test floor division of Hex by a scalar."""
        hex_coord = Hex(5, -2, -3)
        result = hex_coord // 2
        # Floor division should round down
        self.assertEqual(result.i, 2)  # 5 // 2 = 2
        self.assertEqual(result.j, -1)  # -2 // 2 = -1
        # k will be adjusted to maintain constraint
        self.assertEqual(result.i + result.j + result.k, 0)

    def test_hex_equality_same_coordinates(self):
        """Test equality comparison for identical Hex objects."""
        hex1 = Hex(1, -2, 1)
        hex2 = Hex(1, -2, 1)
        self.assertEqual(hex1, hex2)
        self.assertTrue(hex1 == hex2)

    def test_hex_equality_different_coordinates(self):
        """Test equality comparison for different Hex objects."""
        hex1 = Hex(1, -2, 1)
        hex2 = Hex(2, -2, 0)
        self.assertNotEqual(hex1, hex2)
        self.assertFalse(hex1 == hex2)

    def test_hex_equality_with_non_hex(self):
        """Test equality comparison with non-Hex objects."""
        hex_coord = Hex(1, -1, 0)
        self.assertNotEqual(hex_coord, "not a hex")
        self.assertNotEqual(hex_coord, (1, -1, 0))
        self.assertNotEqual(hex_coord, None)

    def test_hex_length_manhattan_distance(self):
        """Test length calculation (Manhattan distance from origin)."""
        # Length should be max(abs(i), abs(j), abs(k))
        hex1 = Hex(3, -2, -1)
        self.assertEqual(len(hex1), 3)  # max(3, 2, 1) = 3

        hex2 = Hex(1, -3, 2)
        self.assertEqual(len(hex2), 3)  # max(1, 3, 2) = 3

        hex3 = Hex(0, 0, 0)
        self.assertEqual(len(hex3), 0)  # origin

    def test_hex_repr(self):
        """Test string representation of Hex objects."""
        hex_coord = Hex(1, -2, 1)
        expected_repr = "Hex(1,-2,1)"
        self.assertEqual(repr(hex_coord), expected_repr)

    def test_hex_hash_consistency(self):
        """Test that equal Hex objects have the same hash."""
        hex1 = Hex(1, -2, 1)
        hex2 = Hex(1, -2, 1)
        self.assertEqual(hash(hex1), hash(hex2))

    def test_hex_hash_different_for_different_coords(self):
        """Test that different Hex objects have different hashes (usually)."""
        hex1 = Hex(1, -2, 1)
        hex2 = Hex(2, -2, 0)
        # Note: Hash collisions are possible but unlikely for different coordinates
        self.assertNotEqual(hash(hex1), hash(hex2))

    def test_hex_can_be_used_as_dict_key(self):
        """Test that Hex objects can be used as dictionary keys."""
        hex1 = Hex(1, -1, 0)
        hex2 = Hex(2, -1, -1)

        hex_dict = {hex1: "first", hex2: "second"}

        self.assertEqual(hex_dict[hex1], "first")
        self.assertEqual(hex_dict[hex2], "second")

    def test_hex_constraint_edge_cases(self):
        """Test constraint enforcement with various edge cases."""
        # Large numbers
        hex_large = Hex(1000, -500, -499)  # k should be adjusted to -500
        self.assertEqual(hex_large.i + hex_large.j + hex_large.k, 0)

        # Negative numbers
        hex_neg = Hex(-5, -3, 10)  # k should be adjusted to 8
        self.assertEqual(hex_neg.i + hex_neg.j + hex_neg.k, 0)

        # Mixed positive/negative
        hex_mixed = Hex(-2, 5, -1)  # k should be adjusted to -3
        self.assertEqual(hex_mixed.i + hex_mixed.j + hex_mixed.k, 0)


if __name__ == "__main__":
    unittest.main()
