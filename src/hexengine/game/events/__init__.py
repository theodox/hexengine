"""Event handling package for game interactions."""

from .mouse import MouseEventHandlerMixin, TargetType
from .hotkey import HotkeyHandlerMixin, Hotkey
from .handler import Modifiers, EventInfo

__all__ = [
    "MouseEventHandlerMixin",
    "TargetType",
    "HotkeyHandlerMixin",
    "Hotkey",
    "Modifiers",
    "EventInfo",
]
