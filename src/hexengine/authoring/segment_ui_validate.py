"""
Load-time validation: declared arc segment ``ui_mode`` values ⊆ title presentation registry (P5).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..arcs.runner import ArcSpec
from ..arcs.spec import Arc, Segment
from ..hooks.core import ENGINE_DEFAULT
from ..hooks.title import TitleHooks


def _ui_mode_from_segment(segment: Segment) -> str | None:
    """Return a segment ``ui_mode`` when it is explicitly set (not internal auto segments)."""

    ui_mode = str(segment.ui_mode or "").strip()
    return ui_mode or None


def ui_modes_from_arc(arc: Arc) -> set[str]:
    """Collect explicit ``ui_mode`` strings from one declared arc."""

    out: set[str] = set()
    for segment in arc.segments:
        ui_mode = _ui_mode_from_segment(segment)
        if ui_mode:
            out.add(ui_mode)
    return out


def collect_declared_ui_modes(bundle: TitleHooks) -> set[str]:
    """
    Union of segment ``ui_mode`` values from the turn routine registry and overlay arcs.

    Segments with an empty ``ui_mode`` (e.g. combat ``classify`` / ``resolve``) are omitted;
    they do not drive per-viewer presentation on the wire.
    """

    ui_modes: set[str] = set()
    reg_raw = bundle.arcs.turn_arc_registry_spec()
    if reg_raw is not ENGINE_DEFAULT:
        from ..arcs.registry import TurnArcRegistry

        if isinstance(reg_raw, TurnArcRegistry):
            for spec in reg_raw.routine_specs.values():
                if isinstance(spec, ArcSpec):
                    ui_modes |= ui_modes_from_arc(spec.arc)

    for _label, spec_raw in (
        ("combat_arc", bundle.arcs.combat_arc_spec()),
        ("movement_arc", bundle.arcs.movement_arc_spec()),
    ):
        if spec_raw is ENGINE_DEFAULT or not isinstance(spec_raw, ArcSpec):
            continue
        ui_modes |= ui_modes_from_arc(spec_raw.arc)
    return ui_modes


def _registry_ui_mode_keys(registry: object) -> tuple[set[str], list[str]]:
    """Normalize hook return value to ui_mode keys; validate row.ui_mode matches dict key."""

    errors: list[str] = []
    if isinstance(registry, Mapping):
        keys: set[str] = set()
        for key, row in registry.items():
            mode_key = str(key).strip()
            if not mode_key:
                errors.append("segment_presentation_registry: empty ui_mode key")
                continue
            keys.add(mode_key)
            row_mode = getattr(row, "ui_mode", None)
            if row_mode is None and isinstance(row, dict):
                row_mode = row.get("ui_mode")
            if row_mode is not None and str(row_mode).strip() != mode_key:
                errors.append(
                    "segment_presentation_registry: "
                    f"key {mode_key!r} row.ui_mode is {row_mode!r}"
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
    Ensure every declared segment ``ui_mode`` has a presentation registry row.

    No-op when the title does not bind ``UIHook.SEGMENT_PRESENTATION_REGISTRY``.
    """

    errors: list[str] = []
    reg_fn = bundle.ui.segment_presentation_registry
    if reg_fn is None:
        return errors

    registry = reg_fn()
    if registry is ENGINE_DEFAULT:
        return errors

    keys, reg_errors = _registry_ui_mode_keys(registry)
    errors.extend(reg_errors)

    declared = collect_declared_ui_modes(bundle)
    missing = sorted(declared - keys)
    if missing:
        errors.append(
            "segment_presentation_registry missing ui_modes used in declared arcs: "
            + ", ".join(missing)
        )

    return errors


def validate_segment_presentation_for_definition(game_definition: Any) -> list[str]:
    from ..hooks.title import read_title_hooks_from_definition

    return validate_segment_presentation(
        read_title_hooks_from_definition(game_definition)
    )


__all__ = [
    "collect_declared_ui_modes",
    "ui_modes_from_arc",
    "validate_segment_presentation",
    "validate_segment_presentation_for_definition",
]
