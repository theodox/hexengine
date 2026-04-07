"""Event handling package for game interactions."""

from __future__ import annotations

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
