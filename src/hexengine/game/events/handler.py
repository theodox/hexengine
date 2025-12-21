"""Event handler data types and utilities."""

from collections import namedtuple
from enum import IntFlag, auto


EventInfo = namedtuple(
    "EventInfo", ["event", "owner", "position", "modifiers", "target", "unit_id", "hex"]
)


class Modifiers(IntFlag):
    NONE = 0
    ALT = auto()
    SHIFT = auto()
    CONTROL = auto()

    @classmethod
    def from_event(cls, event) -> "Modifiers":
        alt = cls.ALT if event.getModifierState("Alt") else 0
        shift = cls.SHIFT if event.getModifierState("Shift") else 0
        control = cls.CONTROL if event.getModifierState("Control") else 0
        return Modifiers(alt | shift | control)
