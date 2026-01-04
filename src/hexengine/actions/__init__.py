"""
Legacy actions package - replaced by hexengine.state.actions.

The old mutable action system (Action, Move, DeleteUnit) has been replaced
by the new immutable state-based action system in hexengine.state.actions
(MoveUnit, DeleteUnit, AddUnit, SpendAction).

This package is kept for backwards compatibility but is empty.
Use: from hexengine.state import MoveUnit, DeleteUnit, etc.
"""

__all__ = []
