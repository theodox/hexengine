"""Event handling package for game interactions."""

from .mouse import EventHandlerMixin, MouseState, TargetType
from .hotkey import HotkeyHandlerMixin

__all__ = [
    "EventHandlerMixin",
    "MouseState",
    "TargetType",
    "HotkeyHandlerMixin",
]
