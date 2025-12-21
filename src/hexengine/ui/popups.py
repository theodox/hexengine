from typing import TYPE_CHECKING

import logging
from ..document import create_proxy, js

if TYPE_CHECKING:
    pass

LOGGER = logging.getLogger("PopupManager")


class PopupManager:
    def __init__(self, canvas) -> None:
        self.canvas = canvas
        self.popups = []

    def add_popup(self, popup: "Popup") -> None:
        self.popups.append(popup)

    def remove_popup(self, popup: "Popup") -> None:
        if popup in self.popups:
            self.popups.remove(popup)

    def get_all_popups(self) -> list["Popup"]:
        return self.popups

    def clear(self) -> None:
        for p in self.popups:
            p.delete(self.canvas)
        self.popups = []

    def create_popup(self, message: str, position: tuple[float, float]) -> "Popup":
        popup = Popup(message, position)
        logging.info(f"Creating popup with message: {message} at position: {position}")
        self.add_popup(popup)
        popup.display(self.canvas)
        return popup


class Popup:
    def __init__(self, message: str, position: tuple[float, float]) -> None:
        self.message = message
        self.position = position
        self.element = None
        self.canvas = None
        self.faded = False
        self.timeout = 0

    def display(self, canvas, timeout: int = 500) -> None:
        div = js.document.createElement("div")
        div.className = "popup"
        div.innerHTML = "<p><b>" + str(self.message) + "</b></p>"
        div.style.left = f"{self.position[0]}px"
        div.style.top = f"{self.position[1]}px"
        canvas.appendChild(div)
        self.element = div
        self.canvas = canvas
        self.timeout = timeout

        if self.timeout:
            self.element.addEventListener(
                "mouseleave", create_proxy(lambda _: self.do_fade())
            )

    def delete(self, *_) -> None:
        LOGGER.info(f"Removing popup with message: {self.message}")
        if self.canvas.contains(self.element):
            self.canvas.removeChild(self.element)

    def do_fade(self, *_) -> None:
        if self.faded:
            return
        logging.getLogger("Popup").info(f"Fading out {self}")
        self.faded = True

        def fade_out(*_):
            self.element.classList.add("fade-out")
            js.setTimeout(create_proxy(lambda: self.delete()), self.timeout)

        js.setTimeout(create_proxy(fade_out), self.timeout)
