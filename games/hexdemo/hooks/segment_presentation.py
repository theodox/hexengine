"""Project hexdemo segment presentation registry onto ``current_segment`` wire."""

from __future__ import annotations

from typing import Any

from hexengine.hooks.ui import UIHook
from hexengine.hooks.ui_segment import SegmentPresentationContext
from hexengine.hooks.wiring import bind_title_hook

from ..segment_ui import resolve_presentation_id, segment_presentation


@bind_title_hook(UIHook.ENRICH_CURRENT_SEGMENT)
def enrich_current_segment(ctx: SegmentPresentationContext) -> dict[str, Any]:
    row = segment_presentation(ctx.segment)
    presentation_id = resolve_presentation_id(
        ctx.segment,
        viewer_may_act=ctx.viewer_may_act,
        current_phase=ctx.current_phase,
    )
    out: dict[str, Any] = {"presentation_id": presentation_id}
    if row is not None:
        if row.interaction_mode:
            out["interaction_mode"] = row.interaction_mode
        out["primitive"] = str(row.primitive.value)
        if row.inform_profile:
            out["inform_profile"] = row.inform_profile
    return out


__all__ = ["enrich_current_segment"]
