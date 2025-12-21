"""Event handling package for game interactions."""

from .mouse import EventHandlerMixin, MouseState, TargetType
from .hotkey import HotkeyHandlerMixin, Hotkey, Modifiers

__all__ = [
    "EventHandlerMixin",
    "MouseState",
    "TargetType",
    "HotkeyHandlerMixin",
    "Hotkey",
    "Modifiers",
]
