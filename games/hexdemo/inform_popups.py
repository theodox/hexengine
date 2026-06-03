"""Map callouts for INFORM ``inform`` inspect requests (attack-plan feedback, etc.)."""

from __future__ import annotations

from hexengine.authoring.present import InformPopup
from hexengine.hooks.inform_popup import InformPopupContext

from .presentation.inform import inform_popup_for_profile


def inform_popup(ctx: InformPopupContext) -> InformPopup:
    profile = str(ctx.inform_profile or ctx.inform_kind or "").strip()
    if profile:
        return inform_popup_for_profile(ctx.shell_ui, profile, ctx.reason)
    return inform_popup_for_profile(ctx.shell_ui, "inform", ctx.reason)


__all__ = ["inform_popup"]
