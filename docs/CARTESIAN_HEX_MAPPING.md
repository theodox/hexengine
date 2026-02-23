# Cartesian to Hex Coordinate Mapping

## Overview

This document explains why multiple integer Cartesian coordinates can map to the same hexagonal coordinate, which is **geometrically correct behavior**.

## The Issue

You may observe that consecutive integer Cartesian coordinates can map to the same hex:

```python
Cartesian(18, 13) -> Hex(12, 2, -14)
Cartesian(18, 14) -> Hex(12, 2, -14)  # Same hex!
```

## Why This Happens

In a flat-top hexagonal grid:

1. **Hex cells are larger than 1x1 unit squares**
   - The vertical distance between hex row centers is √3 ≈ 1.732 units
   - The horizontal distance between hex column centers is 1.5 units

2. **Integer Cartesian coordinates represent discrete points**
   - Points (18, 13) and (18, 14) are 1 unit apart vertically
   - Since hex cells span ~1.73 units vertically, both points fall within the same hex cell

3. **The conversion maps each point to its nearest hex center**
   - Hex(12, 2, -14) has center at approximately (18.0, 13.856)
   - Point (18, 13) is 0.856 units away from this center
   - Point (18, 14) is 0.144 units away from this center
   - Both are closer to this hex than to any other hex

## Visual Representation

```
           Hex Centers (with Cartesian coords)
                    
    y=12.12  ●  Hex(12, 1, -13)
             |
             |  <- 0.88 units
    y=13     +  Cartesian(18, 13)
             |
             |  <- 0.86 units  
    y=13.86  ●  Hex(12, 2, -14)
             |
             |  <- 0.86 units (exactly midpoint between hexes!)
    y=14     +  Cartesian(18, 14)
             |
             
    Vertical spacing between hex centers: √3 ≈ 1.732 units
```

## Implication for `rectangle_from_corners`

The `rectangle_from_corners` function:
1. Converts hex corners to Cartesian coordinates
2. Iterates over all integer Cartesian points in the rectangle
3. Converts each point back to hex coordinates
4. **Now deduplicates** to ensure unique hexes

This deduplication is necessary because the Cartesian grid is denser than the hex grid.

## This Is Correct Behavior

This behavior is **not a bug**. It's a fundamental property of the geometric relationship between:
- A dense integer Cartesian grid (1x1 unit spacing)
- A sparser hexagonal grid (~1.73 unit vertical spacing)

The conversion correctly maps each Cartesian point to its nearest hex based on Voronoi regions.

## Alternative Approaches

If you need a 1:1 mapping between coordinates, you should:

1. **Work directly in hex space** when possible
2. **Use hex-native iteration** (like `radius()`, `ring()`, etc.) instead of Cartesian iteration
3. **Accept deduplication** when working with Cartesian coordinates (as now implemented)
4. **Use floating-point Cartesian coordinates** if you need finer granularity

## Testing

Run the uniqueness tests to verify the mapping behavior:

```bash
python tests/test_uniqueness.py
```

This will show:
- ✓ Hex → Cartesian → Hex round-trips correctly (hex centers preserved)
- Multiple Cartesian points can map to the same hex (expected behavior)
