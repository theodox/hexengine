"""Event handling package for game interactions."""

from .handler import EventInfo, Modifiers
from .hotkey import Hotkey, HotkeyHandlerMixin
from .mouse import MouseEventHandlerMixin

__all__ = [
    "MouseEventHandlerMixin",
    "HotkeyHandlerMixin",
    "Hotkey",
    "Modifiers",
    "EventInfo",
]
