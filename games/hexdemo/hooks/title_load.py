"""
Title-load pack hooks (manifest `[hooks.title_load]`).

Invoked by the engine client title-load arc (`SPLASH`, `SETUP` segments). These are
**not** part of `TitleHooks`; see `hexdemo.hooks.build_hooks` for movement/attack/UI.
"""

from __future__ import annotations

from hexengine.gamedef.title_load import TitleLoadContext, TitleLoadResult


def present_splash(html: str) -> None:
    """Inject pack splash HTML into the client loading overlay."""
    from hexengine.game.title_load_ui import apply_splash_html

    apply_splash_html(html)


def run_setup(ctx: TitleLoadContext) -> TitleLoadResult:
    """Pre-connect setup hook (v1: no UI, always continue)."""
    _ = ctx
    return TitleLoadResult(continue_connect=True)
