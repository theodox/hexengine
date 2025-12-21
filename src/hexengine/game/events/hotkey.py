from typing import Callable
import logging

from ...document import js, create_proxy
from .handler import Modifiers


class HotkeyHandlerMixin:
    """Mixin class providing hotkey handling functionality for the Game class."""

    KEYDOWN_EVENTS = {}

    def on_key_down(self, event) -> None:
        key = event.key.lower()
        modifiers = Modifiers.from_event(event)

        if (key, modifiers) in self.KEYDOWN_EVENTS:
            self.KEYDOWN_EVENTS[(key, modifiers)](self)
            self.logger.info(
                f"Hotkey action for {key} with modifiers {modifiers} executed"
            )

    def _register_hotkeys(self) -> None:
        self.logger.debug("Registering hotkey handlers")
        js.document.onkeydown = create_proxy(lambda event: self.on_key_down(event))


class Hotkey:
    """Represents a hotkey action with associated key, modifiers, and callback."""

    def __init__(self, key: str, modifiers: Modifiers) -> None:
        self.key = key
        self.modifiers = modifiers

    def __call__(self, func: Callable) -> Callable:
        def wrapper(func, *args, **kwds):
            return func(*args, **kwds)

        HotkeyHandlerMixin.KEYDOWN_EVENTS[(self.key, self.modifiers)] = func
        return wrapper


@Hotkey("q", Modifiers.ALT)
def list_hotkeys(*_):
    """List all registered hotkeys."""
    logger = logging.getLogger("game")
    logger.info("Registered Hotkeys:")
    registry = HotkeyHandlerMixin.KEYDOWN_EVENTS
    for (key, modifiers), func in registry.items():
        logger.info(
            f"Hotkey: {key} with Modifiers: {modifiers} -> Function: {func.__name__}"
        )
