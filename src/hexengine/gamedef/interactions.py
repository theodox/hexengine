"""Declarative interaction kinds for engine routing (inspect, markers, etc.)."""

from __future__ import annotations

from enum import StrEnum


class InteractionKind(StrEnum):
    """Stable identifiers for client/engine affordances; Games enable policy per kind."""

    INSPECT_UNIT = "inspect_unit"
    PLACE_MARKER = "place_marker"
