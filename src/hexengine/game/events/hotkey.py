import js                               # type: ignore
from pyodide.ffi import create_proxy    # type: ignore
from ...map.handler import Modifiers

import logging

class HotkeyHandlerMixin:
    """Mixin class providing hotkey handling functionality for the Game class."""
 
    KEYDOWN_EVENTS = {}

    def on_key_down(self, event):

        key = event.key.lower()
        modifiers = Modifiers.from_event(event)

        if (key, modifiers) in self.KEYDOWN_EVENTS:
            self.KEYDOWN_EVENTS[(key, modifiers)](self)
            self.logger.info(f"Hotkey action for {key} with modifiers {modifiers} executed")

    def _register_hotkeys(self):
        self.logger.debug("Registering hotkey handlers")
        js.document.onkeydown = create_proxy(lambda event: self.on_key_down(event))

   
  

class Hotkey:
    """Represents a hotkey action with associated key, modifiers, and callback."""

    def __init__(self, key: str, modifiers: Modifiers):
        self.key = key
        self.modifiers = modifiers

    def __call__(self,func):
        def wrapper(func, *args, **kwds):
            return func(*args, **kwds)        
        HotkeyHandlerMixin.KEYDOWN_EVENTS[(self.key, self.modifiers)] = func
        return wrapper

@Hotkey('q', Modifiers.ALT)
def list_hotkeys(*_):
    """List all registered hotkeys."""
    logger = logging.getLogger("game")
    logger.info("Registered Hotkeys:")
    registry = HotkeyHandlerMixin.KEYDOWN_EVENTS
    for (key, modifiers), func in registry.items():
        logger.info(f"Hotkey: {key} with Modifiers: {modifiers} -> Function: {func.__name__}")
