from .events.hotkey import Hotkey, Modifiers


class GameHistoryMixin:
    """Mixin class providing undo/redo history management using ActionManager."""

    @Hotkey("z", Modifiers.CONTROL)
    def undo_it(self) -> None:
        """Undo the last action using ActionManager."""

        self.logger.warning(f"UNDO, {self.action_mgr}, {self.action_mgr.can_undo()}")
        if hasattr(self, "action_mgr") and self.action_mgr.can_undo():
            self.action_mgr.undo()
            self.logger.info("UNDO")
        else:
            self.logger.debug("No move to undo")

    @Hotkey("y", Modifiers.CONTROL)
    def redo(self) -> None:
        """Redo the next action using ActionManager."""
        if hasattr(self, "action_mgr") and self.action_mgr.can_redo():
            self.action_mgr.redo()
            self.logger.info("REDO")
        else:
            self.logger.debug("No move to redo")
