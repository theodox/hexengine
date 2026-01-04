"""Event handling package for game interactions."""

from .mouse import MouseEventHandlerMixin
from .hotkey import HotkeyHandlerMixin, Hotkey
from .handler import Modifiers, EventInfo

__all__ = [
    "MouseEventHandlerMixin",
    "HotkeyHandlerMixin",
    "Hotkey",
    "Modifiers",
    "EventInfo",
]
