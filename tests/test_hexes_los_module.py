from __future__ import annotations

from hexengine.hexes.los import _ray_hexes, has_line_of_sight
from hexengine.hexes.shapes import radius
from hexengine.hexes.types import Hex


def test_hexes_los_grazing_rule_via_dual_rays() -> None:
    """
    If the centerline rides an edge, one offset ray may be blocked while the other is clear.
    LOS should succeed if *either* offset ray is clear.
    """
    a = Hex(0, 0, 0)

    # Find any target where the two offset discretizations differ (edge-graze case).
    b: Hex | None = None
    for cand in radius(a, 6):
        if cand == a:
            continue
        p1 = _ray_hexes(a, cand, nudge_sign=+1.0)
        p2 = _ray_hexes(a, cand, nudge_sign=-1.0)
        if p1 != p2:
            b = cand
            break

    assert b is not None, "Expected to find an edge-grazing segment within radius"

    p_plus = _ray_hexes(a, b, nudge_sign=+1.0)
    p_minus = _ray_hexes(a, b, nudge_sign=-1.0)
    assert p_plus != p_minus

    plus_mid = set(p_plus[1:-1])
    minus_mid = set(p_minus[1:-1])

    # Choose a blocker that lies on exactly one of the two offset paths.
    only_plus = sorted(plus_mid - minus_mid, key=lambda h: (h.i, h.j, h.k))
    only_minus = sorted(minus_mid - plus_mid, key=lambda h: (h.i, h.j, h.k))
    assert only_plus and only_minus, (
        "Expected each offset path to have unique intermediates"
    )

    blocked = {only_plus[0]}

    def blocks(h: Hex) -> bool:
        return h in blocked

    assert has_line_of_sight(a, b, blocks=blocks) is True

    # Block one unique intermediate on each side => no LOS.
    blocked2 = {only_plus[0], only_minus[0]}

    def blocks2(h: Hex) -> bool:
        return h in blocked2

    assert has_line_of_sight(a, b, blocks=blocks2) is False


def test_hexes_los_edges_block_predicate() -> None:
    a = Hex(0, 0, 0)
    b = Hex(2, 0, -2)

    def edges_block(h1: Hex, h2: Hex) -> bool:
        # Block only the step from origin into the line (first grid edge).
        return h1 == a and h2 == Hex(1, 0, -1)

    def blocks(_h: Hex) -> bool:
        return False

    assert has_line_of_sight(a, b, blocks=blocks, edges_block=edges_block) is False
    assert has_line_of_sight(a, b, blocks=blocks, edges_block=None) is True
