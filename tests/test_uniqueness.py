"""Test if cartesian-to-hex conversion is unique for integer cartesian coordinates."""

from __future__ import annotations

from hexengine.hexes.types import Cartesian, Hex


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
        sample = "; ".join(f"{o} -> {c} -> {b}" for o, c, b in failures[:10])
        raise AssertionError(
            f"Found {len(failures)} round-trip failures (first 10): {sample}"
        )
    print("✓ All hex coordinates round-trip correctly!")


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
        sample = "; ".join(
            f"{h1} and {h2} both -> {c}" for h1, h2, c in collisions[:10]
        )
        raise AssertionError(
            f"Found {len(collisions)} cartesian collisions (first 10): {sample}"
        )
    print("\n✓ No collisions: each hex produces a unique cartesian coordinate!")


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
        sample = "; ".join(
            f"{ca} -> {h1} -> {c2} -> {h2b}" for ca, h1, c2, h2b in inconsistencies[:10]
        )
        raise AssertionError(
            f"Found {len(inconsistencies)} arbitrary-cartesian inconsistencies (first 10): {sample}"
        )
    print("\n✓ Arbitrary cartesian coordinates are consistent!")


if __name__ == "__main__":
    print("Testing cartesian-to-hex uniqueness...\n")
    test_round_trip()
    test_cartesian_uniqueness()
    test_arbitrary_cartesian()
    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED: The conversion is bijective!")
