"""Tests for HexRowCol coordinate system (1:1 mapping with Hex)."""

import sys
sys.path.insert(0, 'src')

from hexengine.hexes.types import Hex, HexRowCol


def test_hex_to_rowcol_to_hex():
    """Test that Hex -> HexRowCol -> Hex is a perfect round trip."""
    test_hexes = [
        Hex(0, 0, 0),
        Hex(5, -3, -2),
        Hex(-4, 7, -3),
        Hex(12, 2, -14),
        Hex(-10, -10, 20),
    ]
    
    for original_hex in test_hexes:
        rowcol = HexRowCol.from_hex(original_hex)
        recovered_hex = rowcol.to_hex()
        assert original_hex == recovered_hex, \
            f"Round trip failed: {original_hex} -> {rowcol} -> {recovered_hex}"
        print(f"✓ {original_hex} ↔ {rowcol}")


def test_rowcol_to_hex_to_rowcol():
    """Test that HexRowCol -> Hex -> HexRowCol is a perfect round trip."""
    test_rowcols = [
        HexRowCol(0, 0),
        HexRowCol(5, 3),
        HexRowCol(-4, 7),
        HexRowCol(2, 12),
        HexRowCol(-10, -10),
    ]
    
    for original_rowcol in test_rowcols:
        hex_coord = original_rowcol.to_hex()
        recovered_rowcol = HexRowCol.from_hex(hex_coord)
        assert original_rowcol == recovered_rowcol, \
            f"Round trip failed: {original_rowcol} -> {hex_coord} -> {recovered_rowcol}"
        print(f"✓ {original_rowcol} ↔ {hex_coord}")


def test_one_to_one_mapping():
    """Verify that the mapping is truly 1:1 (bijective)."""
    # Create a set of hex coordinates
    hex_set = {Hex(i, j, -i-j) for i in range(-5, 6) for j in range(-5, 6)}
    
    # Convert to rowcol
    rowcol_set = {HexRowCol.from_hex(h) for h in hex_set}
    
    # Convert back to hex
    hex_set_recovered = {rc.to_hex() for rc in rowcol_set}
    
    # Should have same number of elements (1:1 mapping)
    assert len(hex_set) == len(rowcol_set), \
        f"Hex->RowCol not injective: {len(hex_set)} hexes -> {len(rowcol_set)} rowcols"
    assert len(rowcol_set) == len(hex_set_recovered), \
        f"RowCol->Hex not injective: {len(rowcol_set)} rowcols -> {len(hex_set_recovered)} hexes"
    assert hex_set == hex_set_recovered, \
        "Round trip doesn't preserve all hexes"
    
    print(f"✓ 1:1 mapping verified for {len(hex_set)} coordinates")


def test_rowcol_arithmetic():
    """Test arithmetic operations on HexRowCol."""
    rc1 = HexRowCol(3, 5)
    rc2 = HexRowCol(2, -1)
    
    # Addition
    result = rc1 + rc2
    assert result == HexRowCol(5, 4), f"Addition failed: {rc1} + {rc2} = {result}"
    print(f"✓ {rc1} + {rc2} = {result}")
    
    # Subtraction
    result = rc1 - rc2
    assert result == HexRowCol(1, 6), f"Subtraction failed: {rc1} - {rc2} = {result}"
    print(f"✓ {rc1} - {rc2} = {result}")


def test_comparison_with_cartesian():
    """Show the difference between Cartesian (many-to-one) and HexRowCol (1:1)."""
    from hexengine.hexes.types import Cartesian
    
    # These two Cartesian coordinates map to the same Hex (as noted in the docs)
    cart1 = Cartesian(18, 13)
    cart2 = Cartesian(18, 14)
    
    hex1 = Hex.from_cartesian(cart1)
    hex2 = Hex.from_cartesian(cart2)
    
    print(f"\nCartesian (many-to-one mapping):")
    print(f"  {cart1} -> {hex1}")
    print(f"  {cart2} -> {hex2}")
    print(f"  Same hex? {hex1 == hex2}")
    
    # HexRowCol has a unique representation for each Hex
    rowcol1 = HexRowCol.from_hex(hex1)
    rowcol2 = HexRowCol.from_hex(hex2)
    
    print(f"\nHexRowCol (1:1 mapping):")
    print(f"  {hex1} -> {rowcol1}")
    print(f"  {hex2} -> {rowcol2}")
    print(f"  Same rowcol? {rowcol1 == rowcol2}")
    
    # And each distinct HexRowCol maps to a distinct Hex
    assert rowcol1 == rowcol2, "Both hexes should map to same rowcol (since they're the same hex)"


if __name__ == "__main__":
    print("Testing HexRowCol coordinate system (1:1 mapping)\n")
    print("=" * 60)
    
    print("\n1. Testing Hex -> HexRowCol -> Hex round trip:")
    test_hex_to_rowcol_to_hex()
    
    print("\n2. Testing HexRowCol -> Hex -> HexRowCol round trip:")
    test_rowcol_to_hex_to_rowcol()
    
    print("\n3. Testing 1:1 mapping property:")
    test_one_to_one_mapping()
    
    print("\n4. Testing HexRowCol arithmetic:")
    test_rowcol_arithmetic()
    
    print("\n5. Comparing Cartesian vs HexRowCol:")
    test_comparison_with_cartesian()
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
