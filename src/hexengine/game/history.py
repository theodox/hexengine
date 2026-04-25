from __future__ import annotations

from .events.hotkey import Hotkey, Modifiers


class GameHistoryMixin:
    """Ctrl+Z / Ctrl+Y hotkeys; ``Game`` implements ``undo`` / ``redo`` (server-backed)."""

    @Hotkey("z", Modifiers.CONTROL)
    def undo_it(self) -> None:
        client = getattr(self, "client", None)
        if client is None or not client.is_my_turn():
            self.logger.warning("Cannot undo: not connected or not your turn")
            return
        self.undo()

    @Hotkey("y", Modifiers.CONTROL)
    def redo_it(self) -> None:
        client = getattr(self, "client", None)
        if client is None or not client.is_my_turn():
            self.logger.warning("Cannot redo: not connected or not your turn")
            return
        self.redo()
