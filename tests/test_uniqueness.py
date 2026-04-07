"""Test if cartesian-to-hex conversion is unique for integer cartesian coordinates."""

from __future__ import annotations

from src.hexengine.hexes.types import Cartesian, Hex


def test_round_trip():
    """Test if hex -> cartesian -> hex produces the same result."""
    failures = []

    # Test a range of hex coordinates
    for i in range(-10, 11):
        for j in range(-10, 11):
            k = -i - j
            hex_orig = Hex(i, j, k)

            # Convert to cartesian and back
            cart = Cartesian.from_hex(hex_orig)
            hex_back = Hex.from_cartesian(cart)

            if hex_orig != hex_back:
                failures.append((hex_orig, cart, hex_back))

    if failures:
        print(f"Found {len(failures)} round-trip failures:")
        for orig, cart, back in failures[:10]:  # Show first 10
            print(f"  {orig} -> {cart} -> {back}")
    else:
        print("✓ All hex coordinates round-trip correctly!")

    return len(failures) == 0


def test_cartesian_uniqueness():
    """Test if different hex coordinates can produce the same cartesian coordinate."""
    cart_to_hex = {}
    collisions = []

    # Generate cartesian coordinates from hex coordinates
    for i in range(-10, 11):
        for j in range(-10, 11):
            k = -i - j
            hex_coord = Hex(i, j, k)
            cart = Cartesian.from_hex(hex_coord)

            if cart in cart_to_hex:
                collisions.append((cart_to_hex[cart], hex_coord, cart))
            else:
                cart_to_hex[cart] = hex_coord

    if collisions:
        print(f"\n✗ Found {len(collisions)} cartesian collisions:")
        for hex1, hex2, cart in collisions[:10]:  # Show first 10
            print(f"  {hex1} and {hex2} both -> {cart}")
    else:
        print("\n✓ No collisions: each hex produces a unique cartesian coordinate!")

    return len(collisions) == 0


def test_arbitrary_cartesian():
    """Test if arbitrary integer cartesian coordinates produce consistent results."""
    inconsistencies = []

    # Test arbitrary cartesian coordinates
    for x in range(-20, 21):
        for y in range(-20, 21):
            cart = Cartesian(x, y)
            hex1 = Hex.from_cartesian(cart)

            # Convert back and forth again
            cart2 = Cartesian.from_hex(hex1)
            hex2 = Hex.from_cartesian(cart2)

            if hex1 != hex2:
                inconsistencies.append((cart, hex1, cart2, hex2))

    if inconsistencies:
        print(
            f"\n✗ Found {len(inconsistencies)} inconsistencies in arbitrary cartesian coords:"
        )
        for cart, hex1, cart2, hex2 in inconsistencies[:10]:
            print(f"  {cart} -> {hex1} -> {cart2} -> {hex2}")
    else:
        print("\n✓ Arbitrary cartesian coordinates are consistent!")

    return len(inconsistencies) == 0


if __name__ == "__main__":
    print("Testing cartesian-to-hex uniqueness...\n")

    result1 = test_round_trip()
    result2 = test_cartesian_uniqueness()
    result3 = test_arbitrary_cartesian()

    print("\n" + "=" * 60)
    if result1 and result2 and result3:
        print("✓ ALL TESTS PASSED: The conversion is bijective!")
    else:
        print("✗ TESTS FAILED: The conversion has issues")
