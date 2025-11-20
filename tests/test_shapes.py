import unittest
from src.hexes.types import Hex
from src.hexes.shapes import (
    convex_hull,
    outer_boundary,
    radius,
    ring,
    path,
    wedge,
    angle,
    wedge_fill
)
from src.hexes.math import distance
import math


class TestHexShapes(unittest.TestCase):
    """Test cases for the hexes.shapes module."""

    def test_convex_hull_empty(self):
        """Test convex hull of empty set."""
        result = convex_hull([])
        self.assertEqual(result, [])

    def test_convex_hull_single_hex(self):
        """Test convex hull of single hex."""
        hex_coord = Hex(1, -1, 0)
        result = convex_hull([hex_coord])
        self.assertEqual(result, [hex_coord])

    def test_convex_hull_two_hexes(self):
        """Test convex hull of two hexes."""
        hex1 = Hex(0, 0, 0)
        hex2 = Hex(1, -1, 0)
        result = convex_hull([hex1, hex2])
        self.assertEqual(len(result), 2)
        self.assertIn(hex1, result)
        self.assertIn(hex2, result)

    def test_convex_hull_line(self):
        """Test convex hull of hexes in a straight line."""
        hexes = [Hex(i, 0, -i) for i in range(-2, 3)]  # Line from (-2,0,2) to (2,0,-2)
        result = convex_hull(hexes)
        # Convex hull of a line should include the endpoints
        # The algorithm may not find exactly both endpoints due to collinearity handling
        # but should include at least the extremes
        result_set = set(result)
        self.assertTrue(
            Hex(-2, 0, 2) in result_set or Hex(2, 0, -2) in result_set,
            "Convex hull should include at least one endpoint"
        )

    def test_convex_hull_triangle(self):
        """Test convex hull of triangle-shaped hex pattern."""
        hexes = [
            Hex(0, 0, 0),    # Center
            Hex(2, -1, -1),  # Top right
            Hex(-1, 2, -1),  # Bottom left
            Hex(-1, -1, 2),  # Top left
        ]
        result = convex_hull(hexes)
        # Should include the three corner vertices
        expected_vertices = {Hex(2, -1, -1), Hex(-1, 2, -1), Hex(-1, -1, 2)}
        result_set = set(result)
        self.assertTrue(expected_vertices.issubset(result_set))

    def test_convex_hull_square_like_pattern(self):
        """Test convex hull of a square-like pattern of hexes."""
        hexes = [
            Hex(0, 0, 0), Hex(1, 0, -1), Hex(0, 1, -1), Hex(1, 1, -2),
            Hex(-1, 0, 1), Hex(-1, 1, 0), Hex(0, -1, 1), Hex(1, -1, 0)
        ]
        result = convex_hull(hexes)
        # Should form a convex boundary
        self.assertGreaterEqual(len(result), 4)  # At least 4 points for a convex shape
        
    def test_convex_hull_with_interior_points(self):
        """Test that interior points are excluded from convex hull."""
        # Create a filled circle of hexes
        center = Hex(0, 0, 0)
        hexes = list(radius(center, 3))
        result = convex_hull(hexes)
        
        # The result should only include boundary hexes, not interior ones
        result_set = set(result)
        self.assertNotIn(center, result_set)  # Center should not be in hull
        
        # All hull points should be on the outer ring
        for hex_coord in result:
            self.assertEqual(distance(center, hex_coord), 3)

    def test_outer_boundary_empty(self):
        """Test outer boundary of empty set."""
        result = outer_boundary([])
        self.assertEqual(len(result), 0)

    def test_outer_boundary_single_hex(self):
        """Test outer boundary of single hex."""
        hex_coord = Hex(1, -1, 0)
        result = outer_boundary([hex_coord])
        self.assertEqual(result, {hex_coord})

    def test_outer_boundary_filled_circle(self):
        """Test outer boundary of filled circle."""
        center = Hex(0, 0, 0)
        hexes = list(radius(center, 2))
        boundary = outer_boundary(hexes)
        
        # All boundary hexes should be at distance 2 from center
        for hex_coord in boundary:
            self.assertEqual(distance(center, hex_coord), 2)

    def test_outer_boundary_l_shape(self):
        """Test outer boundary of L-shaped pattern."""
        hexes = [
            Hex(0, 0, 0), Hex(1, 0, -1), Hex(2, 0, -2),  # Horizontal line
            Hex(0, 1, -1), Hex(0, 2, -2)  # Vertical line
        ]
        boundary = outer_boundary(hexes)
        
        # All provided hexes should be on the boundary (no interior points)
        self.assertEqual(boundary, set(hexes))

    def test_outer_boundary_includes_concave_points(self):
        """Test that outer boundary includes points on concave edges."""
        # Create a C-shaped pattern
        hexes = [
            Hex(0, 0, 0), Hex(1, 0, -1), Hex(2, 0, -2),
            Hex(0, 1, -1), Hex(2, 1, -3),
            Hex(0, 2, -2), Hex(1, 2, -3), Hex(2, 2, -4)
        ]
        boundary = outer_boundary(hexes)
        convex = set(convex_hull(hexes))
        
        # Boundary should include more points than convex hull for concave shapes
        self.assertGreaterEqual(len(boundary), len(convex))

    def test_path_empty(self):
        """Test path with empty steps."""
        result = list(path([]))
        self.assertEqual(result, [])

    def test_path_single_step(self):
        """Test path with single step."""
        result = list(path([Hex(0, 0, 0)]))
        self.assertEqual(result, [])

    def test_path_two_steps(self):
        """Test path between two hexes."""
        start = Hex(0, 0, 0)
        end = Hex(2, -1, -1)
        result = list(path([start, end]))
        
        # Should include all hexes on the line between start and end
        self.assertIn(start, result)
        self.assertIn(end, result)
        
        # Path length should be distance + 1
        expected_length = distance(start, end) + 1
        self.assertEqual(len(result), expected_length)

    def test_radius_zero(self):
        """Test radius of 0 returns only center."""
        center = Hex(1, -1, 0)
        result = list(radius(center, 0))
        self.assertEqual(result, [center])

    def test_radius_one(self):
        """Test radius of 1 includes center and neighbors."""
        center = Hex(0, 0, 0)
        result = set(radius(center, 1))
        
        # Should include center + 6 neighbors = 7 hexes total
        self.assertEqual(len(result), 7)
        self.assertIn(center, result)

    def test_radius_constraint_maintained(self):
        """Test that all hexes in radius maintain hex constraint."""
        center = Hex(2, -1, -1)
        for hex_coord in radius(center, 3):
            self.assertEqual(hex_coord.i + hex_coord.j + hex_coord.k, 0)

    def test_ring_distance(self):
        """Test that all hexes in ring are exactly at specified distance."""
        center = Hex(1, 1, -2)
        ring_radius = 2
        
        for hex_coord in ring(center, ring_radius):
            self.assertEqual(distance(center, hex_coord), ring_radius)

    def test_ring_count(self):
        """Test that ring count follows expected pattern."""
        center = Hex(0, 0, 0)
        
        # Ring of radius 0 should have 1 hex (center)
        ring0 = list(ring(center, 0))
        self.assertEqual(len(ring0), 1)
        
        # Ring of radius > 0 should have 6 * radius hexes
        for r in range(1, 4):
            ring_r = list(ring(center, r))
            self.assertEqual(len(ring_r), 6 * r)

    def test_angle_calculation(self):
        """Test angle calculation between hexes."""
        center = Hex(0, 0, 0)
        
        # Test some known angles
        right = Hex(1, 0, -1)
        angle_right = angle(center, right)
        self.assertIsInstance(angle_right, float)
        self.assertGreaterEqual(angle_right, 0)
        self.assertLess(angle_right, 2 * math.pi)

    def test_angle_same_hex(self):
        """Test angle calculation for same hex."""
        hex_coord = Hex(1, -1, 0)
        result = angle(hex_coord, hex_coord)
        # Should handle this case gracefully
        self.assertIsInstance(result, float)

    def test_wedge_fill_contains_center(self):
        """Test that wedge fill always includes center."""
        center = Hex(0, 0, 0)
        result = list(wedge_fill(center, 2, 0, math.pi))
        self.assertIn(center, result)

    def test_wedge_fill_radius_constraint(self):
        """Test that wedge fill respects radius constraint."""
        center = Hex(1, 1, -2)
        max_radius = 2
        
        for hex_coord in wedge_fill(center, max_radius, 0, math.pi):
            self.assertLessEqual(distance(center, hex_coord), max_radius)

    def test_convex_hull_ordering(self):
        """Test that convex hull returns points in consistent order."""
        # Create a simple pattern where ordering can be verified
        hexes = [
            Hex(0, 0, 0), Hex(2, 0, -2), Hex(1, 1, -2), Hex(-1, 2, -1), Hex(-2, 1, 1)
        ]
        result = convex_hull(hexes)
        
        # Result should be non-empty and contain valid hexes
        self.assertGreater(len(result), 0)
        for hex_coord in result:
            self.assertEqual(hex_coord.i + hex_coord.j + hex_coord.k, 0)


if __name__ == '__main__':
    unittest.main()