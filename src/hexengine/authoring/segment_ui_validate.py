"""
Load-time validation: declared arc segment ``kind`` values ⊆ title presentation registry (P5).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..arcs.runner import ArcSpec
from ..arcs.spec import Arc, Segment
from ..hooks.core import ENGINE_DEFAULT
from ..hooks.title import TitleHooks


def _kind_from_segment(segment: Segment) -> str | None:
    """Return a segment ``kind`` when it is explicitly set (not internal auto segments)."""

    kind = str(segment.kind or "").strip()
    return kind or None


def kinds_from_arc(arc: Arc) -> set[str]:
    """Collect explicit ``kind`` strings from one declared arc."""

    out: set[str] = set()
    for segment in arc.segments:
        kind = _kind_from_segment(segment)
        if kind:
            out.add(kind)
    return out


def collect_declared_segment_kinds(bundle: TitleHooks) -> set[str]:
    """
    Union of segment ``kind`` values from the turn routine registry and overlay arcs.

    Segments with an empty ``kind`` (e.g. combat ``classify`` / ``resolve``) are omitted;
    they do not drive per-viewer presentation on the wire.
    """

    kinds: set[str] = set()
    reg_raw = bundle.arcs.turn_arc_registry_spec()
    if reg_raw is not ENGINE_DEFAULT:
        from ..arcs.registry import TurnArcRegistry

        if isinstance(reg_raw, TurnArcRegistry):
            for spec in reg_raw.routine_specs.values():
                if isinstance(spec, ArcSpec):
                    kinds |= kinds_from_arc(spec.arc)

    for _label, spec_raw in (
        ("combat_arc", bundle.arcs.combat_arc_spec()),
        ("movement_arc", bundle.arcs.movement_arc_spec()),
    ):
        if spec_raw is ENGINE_DEFAULT or not isinstance(spec_raw, ArcSpec):
            continue
        kinds |= kinds_from_arc(spec_raw.arc)
    return kinds


def _registry_kind_keys(registry: object) -> tuple[set[str], list[str]]:
    """Normalize hook return value to kind keys; validate row.kind matches dict key."""

    errors: list[str] = []
    if isinstance(registry, Mapping):
        keys: set[str] = set()
        for key, row in registry.items():
            kind_key = str(key).strip()
            if not kind_key:
                errors.append("segment_presentation_registry: empty kind key")
                continue
            keys.add(kind_key)
            row_kind = getattr(row, "kind", None)
            if row_kind is None and isinstance(row, dict):
                row_kind = row.get("kind")
            if row_kind is not None and str(row_kind).strip() != kind_key:
                errors.append(
                    "segment_presentation_registry: "
                    f"key {kind_key!r} row.kind is {row_kind!r}"
                )
        return keys, errors
    if isinstance(registry, set | frozenset):
        keys = {str(k).strip() for k in registry if str(k).strip()}
        return keys, errors
    errors.append(
        "segment_presentation_registry hook must return a mapping, set, or frozenset"
    )
    return set(), errors


def validate_segment_presentation(bundle: TitleHooks) -> list[str]:
    """
    Ensure every declared segment ``kind`` has a presentation registry row.

    No-op when the title does not bind ``UIHook.SEGMENT_PRESENTATION_REGISTRY``.
    """

    errors: list[str] = []
    reg_fn = bundle.ui.segment_presentation_registry
    if reg_fn is None:
        return errors

    registry = reg_fn()
    if registry is ENGINE_DEFAULT:
        return errors

    keys, reg_errors = _registry_kind_keys(registry)
    errors.extend(reg_errors)

    declared = collect_declared_segment_kinds(bundle)
    missing = sorted(declared - keys)
    if missing:
        errors.append(
            "segment_presentation_registry missing kinds used in declared arcs: "
            + ", ".join(missing)
        )

    return errors


def validate_segment_presentation_for_definition(game_definition: Any) -> list[str]:
    from ..hooks.title import read_title_hooks_from_definition

    return validate_segment_presentation(
        read_title_hooks_from_definition(game_definition)
    )


__all__ = [
    "collect_declared_segment_kinds",
    "kinds_from_arc",
    "validate_segment_presentation",
    "validate_segment_presentation_for_definition",
]
