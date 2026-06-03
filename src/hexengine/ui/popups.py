from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..document import create_proxy, js

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger("PopupManager")

# Must match ``fadeOut`` duration in ``hexes.css``.
_FADE_MS = 500


class PopupManager:
    def __init__(self, canvas) -> None:
        self.canvas = canvas
        self.popups = []

    def add_popup(self, popup: Popup) -> None:
        self.popups.append(popup)

    def remove_popup(self, popup: Popup) -> None:
        if popup in self.popups:
            self.popups.remove(popup)

    def get_all_popups(self) -> list[Popup]:
        return self.popups

    def clear(self) -> None:
        for p in self.popups:
            p.delete(self.canvas)
        self.popups = []

    def create_popup(
        self,
        message: str,
        position: tuple[float, float],
        *,
        timeout_ms: int | None = None,
        css_class: str | None = None,
        auto_dismiss: bool = False,
    ) -> Popup:
        self.clear()
        popup = Popup(message, position)
        logging.info(f"Creating popup with message: {message} at position: {position}")
        self.add_popup(popup)
        timeout = 500 if timeout_ms is None else max(0, int(timeout_ms))
        popup.display(
            self.canvas,
            timeout=timeout,
            css_class=css_class,
            auto_dismiss=auto_dismiss,
        )
        return popup

    def create_popup_html(
        self,
        html: str,
        position: tuple[float, float],
        *,
        timeout_ms: int | None = None,
        css_class: str | None = None,
        auto_dismiss: bool = False,
    ) -> Popup:
        self.clear()
        popup = Popup(html, position, is_html=True)
        self.add_popup(popup)
        timeout = 500 if timeout_ms is None else max(0, int(timeout_ms))
        popup.display(
            self.canvas,
            timeout=timeout,
            css_class=css_class,
            auto_dismiss=auto_dismiss,
        )
        return popup


class Popup:
    def __init__(
        self, message: str, position: tuple[float, float], *, is_html: bool = False
    ) -> None:
        self.message = message
        self.position = position
        self.is_html = bool(is_html)
        self.element = None
        self.canvas = None
        self.faded = False
        self.timeout = 0

    def display(
        self,
        canvas,
        timeout: int = 500,
        *,
        css_class: str | None = None,
        auto_dismiss: bool = False,
    ) -> None:
        # Root is the callout anchor: (left, top) is the map pixel under the tail tip
        # (e.g. unit center). Bubble sits above; tail points down to that point.
        # @TODO: position popups as close to screen center as possible,
        # including below the mouse cursor if position would clip the screen
        root = js.document.createElement("div")
        extra = str(css_class).strip() if css_class is not None else ""
        root.className = (
            f"popup popup--callout {extra}".strip() if extra else "popup popup--callout"
        )

        bubble = js.document.createElement("div")
        bubble.className = "popup-bubble"
        if self.is_html:
            bubble.innerHTML = str(self.message)
        else:
            p = js.document.createElement("p")
            b = js.document.createElement("b")
            b.textContent = str(self.message)
            p.appendChild(b)
            bubble.appendChild(p)

        tail = js.document.createElement("div")
        tail.className = "popup-tail"
        tail.setAttribute("aria-hidden", "true")

        root.appendChild(bubble)
        root.appendChild(tail)

        root.style.left = f"{self.position[0]}px"
        root.style.top = f"{self.position[1]}px"
        canvas.appendChild(root)
        self.element = root
        self.canvas = canvas
        self.timeout = max(0, int(timeout))

        if auto_dismiss:
            delay = self.timeout
            js.setTimeout(create_proxy(self._dismiss_after_ttl), delay)
        else:
            self.element.addEventListener(
                "mouseleave", create_proxy(self._dismiss_on_mouseleave)
            )

    def _dismiss_after_ttl(self, *_args: object) -> None:
        self._begin_fade_out()

    def _dismiss_on_mouseleave(self, *_args: object) -> None:
        self._begin_fade_out()

    def _begin_fade_out(self) -> None:
        if self.faded:
            return
        self.faded = True
        el = self.element
        if el is None:
            return
        logging.getLogger("Popup").info("Fading out %s", self)
        el.classList.add("fade-out")
        js.setTimeout(create_proxy(self.delete), _FADE_MS)

    def delete(self, *_args: object) -> None:
        LOGGER.info(f"Removing popup with message: {self.message}")
        el = self.element
        canvas = self.canvas
        if el is not None and canvas is not None:
            try:
                if canvas.contains(el):
                    canvas.removeChild(el)
            except Exception:
                pass

    def do_fade(self, *_args: object) -> None:
        """Legacy entry point; prefer ``_begin_fade_out``."""
        self._begin_fade_out()
