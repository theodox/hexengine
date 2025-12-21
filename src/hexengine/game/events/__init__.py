"""Event handling package for game interactions."""

from .mouse import EventHandlerMixin, TargetType
from .hotkey import HotkeyHandlerMixin, Hotkey
from .handler import Modifiers, EventInfo

__all__ = [
    "EventHandlerMixin",
    "TargetType",
    "HotkeyHandlerMixin",
    "Hotkey",
    "Modifiers",
    "EventInfo",
]
