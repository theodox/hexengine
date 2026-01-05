import logging

from ..document import create_proxy
from ..game.events.handler import EventInfo, Modifiers
import js
from pyodide.ffi import jsnull

HANDLER_LOGGER = logging.getLogger("handler")
HANDLER_LOGGER.setLevel(logging.DEBUG)


class MouseHandler:
    """
    Event handler for UI events on an owner element.
    """

    def __init__(self, owner, event_type: str, layout=None) -> None:
        self._handlers = []
        self._owner = owner
        self._event_type = event_type
        self._layout = layout
        self.proxy = create_proxy(self._handle_event)
        self._owner.addEventListener(event_type, self.proxy)

    def _get_event_target(self, event) -> tuple:
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
        depth = 0
        while target and not unit_id and depth < 10:
            try:
                # Log what we're checking
                tag = target.tagName if hasattr(target, 'tagName') else 'unknown'
                elem_id = target.id if hasattr(target, 'id') else ''
                
                unit_id = target.getAttribute("data-unit")
                if unit_id and unit_id != jsnull:
                    break
            except Exception as e:
                HANDLER_LOGGER.error(f"[Handler] Error at depth {depth}: {e}")
            
            target = target.parentElement
            depth += 1

        if not unit_id:
            HANDLER_LOGGER.debug("[Handler] No unit_id found after walking DOM tree")
        
        if unit_id == jsnull:
            unit_id = None
        return target, unit_id

    def _handle_event(self, event) -> None:
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
        
        
        for i, handler in enumerate(self._handlers):
            try:
                handler(result)
            except Exception as e:
                HANDLER_LOGGER.error(f"[Handler] Error in handler {i}: {e}")

    def __lt__(self, handler):
        # use < to add a mouse handler
        HANDLER_LOGGER.debug(f"Adding handler {handler} to {self}")
        self._handlers.append(create_proxy(handler))
        return self

    def __isub__(self, handler):
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<MouseHandler event_type={self._event_type} owner={self._owner}>"
