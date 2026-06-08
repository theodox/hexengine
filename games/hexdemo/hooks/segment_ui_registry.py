"""Expose ``segment_ui`` registry for load-time validation (P5)."""

from __future__ import annotations

from hexengine.hooks.ui import UIHook
from hexengine.hooks.wiring import bind_title_hook

from ..ui.segment_registry import PRESENTATION_BY_UI_MODE


@bind_title_hook(UIHook.SEGMENT_PRESENTATION_REGISTRY)
def segment_presentation_registry():
    """Return the pack segment presentation registry for ``validate_title_contract``."""

    return PRESENTATION_BY_UI_MODE


__all__ = ["segment_presentation_registry"]
