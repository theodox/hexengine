"""
Pure queries over board edge/centerline primitives (geometry only; titles interpret tags).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from ..hexes.centerline import consecutive_step_on_path
from ..hexes.edges import EdgeKey, edge_between
from ..hexes.shapes import hex_line_segment
from ..hexes.types import Hex
from .game_state import BoardEdgeFeature, BoardLinearFeature, BoardState


def edge_keys_along_hex_line(a: Hex, b: Hex) -> tuple[EdgeKey, ...]:
    """Undirected edges crossed by the hex-grid segment from a to b (consecutive hex steps)."""
    seg = list(hex_line_segment(a, b))
    out: list[EdgeKey] = []
    for i in range(len(seg) - 1):
        e = edge_between(seg[i], seg[i + 1])
        if e is not None:
            out.append(e)
    return tuple(out)


def board_edge_features_along_hex_line(
    board: BoardState, a: Hex, b: Hex
) -> tuple[BoardEdgeFeature, ...]:
    """Edge primitives sitting on any edge crossed by the hex line segment a→b."""
    keys = frozenset(edge_keys_along_hex_line(a, b))
    return tuple(f for f in board.edge_features if f.edge_key in keys)


def linear_features_on_neighbor_step(
    board: BoardState, from_hex: Hex, to_hex: Hex
) -> tuple[BoardLinearFeature, ...]:
    """Centerline rows whose spine includes this neighbor step (either direction along path)."""
    return tuple(
        f
        for f in board.linear_features
        if consecutive_step_on_path(f.path_hexes, from_hex, to_hex)
    )


def edge_los_blocking_tags(board: BoardState) -> frozenset[str]:
    """Tags for which ``edge_line_of_sight_by_tag`` is true (LOS blocked on crossing)."""
    return frozenset(t for t, v in board.edge_line_of_sight_by_tag if v)


def edges_block_los_predicate(board: BoardState) -> Callable[[Hex, Hex], bool] | None:
    """Return ``(h1, h2) -> True`` when the grid step h1→h2 crosses a LOS-blocking edge.

    Expands non-adjacent ``h1``/``h2`` along ``hex_line_segment``. Returns ``None`` when
    no edge tags block LOS (callers may omit ``edges_block`` on LOS helpers).
    """
    blocking = edge_los_blocking_tags(board)
    if not blocking:
        return None

    def pred(h1: Hex, h2: Hex) -> bool:
        seg = list(hex_line_segment(h1, h2))
        for i in range(len(seg) - 1):
            ek = edge_between(seg[i], seg[i + 1])
            if ek is None:
                continue
            for feat in board.edge_map_features_at(ek):
                for tag in feat.tags:
                    if str(tag).strip() in blocking:
                        return True
        return False

    return pred


def edge_line_of_sight_blocks_hex_line(board: BoardState, a: Hex, b: Hex) -> bool:
    """True if any edge crossed by the straight hex-grid segment ``a``→``b`` blocks LOS."""
    pred = edges_block_los_predicate(board)
    if pred is None:
        return False
    seg = list(hex_line_segment(a, b))
    for i in range(len(seg) - 1):
        if pred(seg[i], seg[i + 1]):
            return True
    return False


def edge_movement_extra_for_neighbor_step(
    board: BoardState, from_hex: Hex, to_hex: Hex
) -> float:
    """Sum configured extras for each tag on ``[[edge_features]]`` along this neighbor step."""
    if not board.edge_movement_extra_by_tag:
        return 0.0
    table = dict(board.edge_movement_extra_by_tag)
    ek = edge_between(from_hex, to_hex)
    if ek is None:
        return 0.0
    extra = 0.0
    for feat in board.edge_map_features_at(ek):
        for tag in feat.tags:
            t = str(tag).strip()
            if t in table:
                extra += float(table[t])
    return extra


def min_linear_movement_cost_for_tags(
    board: BoardState, tags: Iterable[str],
) -> float | None:
    """Smallest configured per-tag linear step cost among ``tags``.

    Returns ``None`` when no tag has an entry (caller should use destination terrain cost).
    """
    if not board.linear_movement_by_tag:
        return None
    table = dict(board.linear_movement_by_tag)
    best: float | None = None
    for t in tags:
        s = str(t).strip()
        if s in table:
            c = table[s]
            best = c if best is None else min(best, c)
    return best
