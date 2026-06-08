"""Marker map-selection preview hook."""

from __future__ import annotations

from hexengine.hooks.ui import UIHook
from hexengine.hooks.wiring import bind_title_hook

from ..ui.previews.place_marker import place_marker_preview


@bind_title_hook(UIHook.PLACE_MARKER_PREVIEW)
def place_marker_preview_for_viewer(ctx):
    return place_marker_preview(ctx)


__all__ = ["place_marker_preview_for_viewer"]
