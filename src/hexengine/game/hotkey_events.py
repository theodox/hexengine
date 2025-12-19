import js
from pyodide.ffi import create_proxy
from ..map.handler import Modifiers


class HotkeyHandlerMixin:
    """Mixin class providing hotkey handling functionality for the Game class."""

    def on_key_down(self, event):
        key = event.key.lower()
        modifiers = Modifiers.from_event(event)
        self.logger.debug(f"Key down: {key} with modifiers {modifiers}")

        # Example hotkey: 'z' for undo with Ctrl modifier
        if key == "z" and (modifiers & Modifiers.CONTROL):
            self.undo()
            self.logger.info("Undo action triggered")

        # Example hotkey: 'y' for redo with Ctrl modifier
        if key == "y" and (modifiers & Modifiers.CONTROL):
            self.redo()
            self.logger.info("Redo action triggered")

    def register_hotkeys(self):
        self.logger.debug("Registering hotkey handlers")
        js.document.onkeydown = create_proxy(lambda event: self.on_key_down(event))
