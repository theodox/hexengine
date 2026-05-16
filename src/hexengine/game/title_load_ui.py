"""DOM helpers for the `#loading` title-load splash (Pyodide client)."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_LOADING_ID = "loading"
_ACTIVE_CLASS = "hexengine-splash-active"
_CSS_VAR = "--hexengine-splash-dismiss-delay-ms"
_DEFAULT_DISMISS_MS = 480
_FADE_MS = 280


def _panel():
    try:
        from ..document import element

        return element(_LOADING_ID)
    except Exception:
        return None


def apply_splash_html(html: str) -> None:
    """Show pack splash HTML in `#loading`. No-op when the document is unavailable."""
    panel = _panel()
    if panel is None:
        return
    try:
        from ..document import jsnull

        panel.innerHTML = html
        panel.style.display = "flex"
        panel.style.zIndex = "2500"
        if (
            getattr(panel, "classList", None) is not None
            and panel.classList is not jsnull
        ):
            panel.classList.add(_ACTIVE_CLASS)
    except Exception:
        logger.debug("apply_splash_html failed", exc_info=True)


def dismiss_splash_after_ready() -> None:
    """Hide `#loading` after first authoritative state (reads CSS var for hold time)."""
    panel = _panel()
    if panel is None:
        return
    if getattr(panel, "_hexengine_splash_dismiss_started", False):
        return

    def _begin() -> None:
        try:
            from ..document import create_proxy, js, jsnull

            if getattr(panel, "_hexengine_splash_dismiss_started", False):
                return
            panel._hexengine_splash_dismiss_started = True

            hold_ms = _DEFAULT_DISMISS_MS
            try:
                raw = js.getComputedStyle(panel).getPropertyValue(_CSS_VAR)
                s = str(raw).strip().lower().replace(",", "")
                if s.endswith("ms"):
                    hold_ms = max(0, int(float(s[:-2].strip())))
                elif s.endswith("s"):
                    hold_ms = max(0, int(float(s[:-1].strip()) * 1000.0))
                elif s:
                    hold_ms = max(0, int(float(s)))
            except (TypeError, ValueError):
                pass

            def _fade_out() -> None:
                try:
                    if (
                        getattr(panel, "classList", None) is not None
                        and panel.classList is not jsnull
                    ):
                        panel.classList.add("hexengine-splash-dismissing")
                        panel.classList.remove(_ACTIVE_CLASS)

                    def _hide() -> None:
                        panel.style.display = "none"
                        panel._hexengine_splash_dismiss_started = False

                    js.setTimeout(create_proxy(_hide), _FADE_MS)
                except Exception:
                    panel.style.display = "none"

            js.setTimeout(create_proxy(_fade_out), hold_ms)
        except Exception:
            logger.debug("dismiss_splash_after_ready failed", exc_info=True)
            try:
                panel.style.display = "none"
            except Exception:
                pass

    try:
        from ..document import create_proxy, js

        js.requestAnimationFrame(create_proxy(lambda _t: _begin()))
    except Exception:
        _begin()


def force_hide_splash() -> None:
    """Hide splash immediately (connect failure / disconnect)."""
    panel = _panel()
    if panel is None:
        return
    try:
        from ..document import jsnull

        panel.style.display = "none"
        if (
            getattr(panel, "classList", None) is not None
            and panel.classList is not jsnull
        ):
            panel.classList.remove(_ACTIVE_CLASS, "hexengine-splash-dismissing")
        panel._hexengine_splash_dismiss_started = False
    except Exception:
        pass


__all__ = [
    "apply_splash_html",
    "dismiss_splash_after_ready",
    "force_hide_splash",
]
