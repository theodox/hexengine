"""Wire normalization helpers for Attack RPC params (title allowlist)."""

from __future__ import annotations

from typing import Any

from ...hexes.types import Hex
from ...state import GameState


def dedupe_wire_id_list(raw: Any) -> list[str]:
    """Stable de-dupe of string ids from a wire list field."""
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for x in raw:
        if isinstance(x, str) and (s := x.strip()) and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def normalize_attack_party_ids(
    params: dict[str, Any], *, anchor_id: str, plural_key: str
) -> tuple[str, ...]:
    """Build ordered (anchor first) party ids from wire anchor + optional plural list."""
    anchor = str(anchor_id or "").strip()
    if not anchor:
        return ()
    extras = dedupe_wire_id_list(params.get(plural_key))
    if not extras:
        return (anchor,)
    if anchor not in extras:
        return (anchor, *extras)
    rest = [x for x in extras if x != anchor]
    return (anchor, *rest)


def sorted_unique_hexes_from_unit_ids(
    state: GameState, unit_ids: tuple[str, ...]
) -> tuple[Hex, ...]:
    """Distinct hex positions of active units with the given ids (sorted for stability)."""
    seen: set[tuple[int, int, int]] = set()
    hs: list[Hex] = []
    for uid in unit_ids:
        u = state.board.units.get(uid)
        if u is None or not u.active:
            continue
        t = (int(u.position.i), int(u.position.j), int(u.position.k))
        if t in seen:
            continue
        seen.add(t)
        hs.append(u.position)
    return tuple(sorted(hs, key=lambda h: (int(h.i), int(h.j), int(h.k))))


def optional_wire_hex_frozenset(
    params: dict[str, Any], key: str
) -> frozenset[Hex] | None:
    """If params[key] is a list of {i,j,k}, return those hexes; else None."""
    raw = params.get(key)
    if not isinstance(raw, list) or not raw:
        return None
    out: list[Hex] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            out.append(Hex(int(row["i"]), int(row["j"]), int(row["k"])))
        except (KeyError, TypeError, ValueError):
            continue
    return frozenset(out) if out else None


__all__ = [
    "dedupe_wire_id_list",
    "normalize_attack_party_ids",
    "optional_wire_hex_frozenset",
    "sorted_unique_hexes_from_unit_ids",
]
