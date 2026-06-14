"""
Title-pack allowlist for arc runtime helpers.

Import submodules directly (the package root does not re-export symbols, to avoid
import cycles through hooks):

    from hexengine.arcs.title.lookup import attach_arc_lookup
    from hexengine.arcs.title.attack_commit import build_attack_context_from_wire
    from hexengine.arcs.title.segment import segment_allows_action

Shared declarative types (Arc, ArcContext, ArcSpec, …) remain on hexengine.arcs.
Titles must not import hexengine.server for arc lookup, attack commit, or segment
projection.
"""

from __future__ import annotations

__all__: list[str] = []
