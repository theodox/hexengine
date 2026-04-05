from .events.hotkey import Hotkey, Modifiers


class GameHistoryMixin:
    """Mixin class providing undo/redo history management using ActionManager."""

    @Hotkey("z", Modifiers.CONTROL)
    def undo_it(self) -> None:
        """Undo the last action. Subclasses can override undo() for custom behavior."""
        if self.client.is_my_turn():
            self.undo()
        else:
            self.logger.warning("Cannot undo: not your turn")

    @Hotkey("y", Modifiers.CONTROL)
    def redo_it(self) -> None:
        """Redo the next action. Subclasses can override redo() for custom behavior."""
        if self.client.is_my_turn():
            self.redo()
        else:
            self.logger.warning("Cannot redo: not your turn")

    def undo(self) -> None:
        """Default undo implementation using ActionManager. Subclasses can override."""
        if hasattr(self, "action_mgr") and self.action_mgr.can_undo():
            self.action_mgr.undo()
            self.logger.info("Undid action")
        else:
            self.logger.debug("No move to undo")

    def redo(self) -> None:
        """Default redo implementation using ActionManager. Subclasses can override."""
        if hasattr(self, "action_mgr") and self.action_mgr.can_redo():
            self.action_mgr.redo()
            self.logger.info("Redid action")
        else:
            self.logger.debug("No move to redo")
