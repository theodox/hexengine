import logging
from pyodide.ffi import create_proxy
from enum import IntFlag, auto

from collections import namedtuple

HANDLER_LOGGER = logging.getLogger("handler")
HANDLER_LOGGER.setLevel(logging.DEBUG)

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


class Handler:
    """
    Event handler for UI events on an owner element.
    """

    def __init__(self, owner, event_type: str, layout=None):
        self._handlers = []
        self._owner = owner
        self._event_type = event_type
        self._layout = layout
        self.proxy = create_proxy(self._handle_event)
        self._owner.addEventListener(event_type, self.proxy)

    def _get_event_target(self, event):
        """
        Extract target information from a DOM event.
        Returns a tuple of (target_element, unit_id) where:
        - target_element: the DOM element that was clicked
        - unit_id: the data-unit attribute value if present, None otherwise

        This walks up the DOM tree to find an element with a data-unit attribute.
        """
        target = event.target
        unit_id = None

        # Walk up the DOM tree to find an element with data-unit attribute
        while target and not unit_id:
            unit_id = target.getAttribute("data-unit")
            if unit_id:
                break
            target = target.parentElement

        return target, unit_id

    def _handle_event(self, event):
        # handle the click coordinates for canvas elements
        # Always use owner's bounding box for consistent coordinate system
        rect = self._owner.getBoundingClientRect()
        x = event.clientX - rect.left
        y = event.clientY - rect.top
        if hasattr(self._owner, "width"):
            sx = self._owner.width / rect.width
        else:
            sx = 1.0

        if hasattr(self._owner, "height"):
            sy = self._owner.height / rect.height
        else:
            sy = 1.0

        modifiers = Modifiers.from_event(event)
        target, unit_id = self._get_event_target(event)
        
        # Compute hex from position if layout is available
        position = (x * sx, y * sy)
        hex_value = self._layout.pixel_to_hex(*position) if self._layout else None

        result = EventInfo(
            event=event,
            owner=self._owner,
            position=position,
            modifiers=modifiers,
            target=target,
            unit_id=unit_id,
            hex=hex_value,
        )
        for handler in self._handlers:
            handler(result)

    def __lt__(self, handler):
        # use < to add a handler
        logging.getLogger().debug(f"Adding handler {handler} to {self}")
        self._handlers.append(create_proxy(handler))
        return self

    def __isub__(self, handler):
        raise NotImplemented

    def __repr__(self):
        return f"<Handler event_type={self._event_type} owner={self._owner}>"
