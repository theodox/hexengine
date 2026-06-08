"""Project hexdemo segment presentation registry onto ``current_segment`` wire."""

from __future__ import annotations

from hexengine.hooks.ui import UIHook
from hexengine.hooks.ui_segment import (
    SegmentPresentationContext,
    SegmentPresentationPatch,
    segment_presentation_patch,
)
from hexengine.hooks.wiring import bind_title_hook

from ..ui.segment_registry import resolve_presentation_id, segment_presentation


@bind_title_hook(UIHook.ENRICH_CURRENT_SEGMENT)
def enrich_current_segment(ctx: SegmentPresentationContext) -> SegmentPresentationPatch:
    row = segment_presentation(ctx.segment)
    presentation_id = resolve_presentation_id(
        ctx.segment,
        viewer_may_act=ctx.viewer_may_act,
        current_phase=ctx.current_phase,
    )
    if row is None:
        return segment_presentation_patch(presentation_id=presentation_id)
    return segment_presentation_patch(
        presentation_id=presentation_id,
        interaction_mode=row.interaction_mode,
        draft_presentation_id=row.draft_presentation_id,
        primitive=str(row.primitive.value),
        inform_profile=row.inform_profile,
    )


__all__ = ["enrich_current_segment"]
