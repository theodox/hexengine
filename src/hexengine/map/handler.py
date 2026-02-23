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

    def __init__(self, owner, event_type: str, layout=None, map_instance=None) -> None:
        self._handlers = []
        self._owner = owner
        self._event_type = event_type
        self._layout = layout
        self._map = map_instance  # Reference to Map for zoom/pan transforms
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
                tag = target.tagName if hasattr(target, "tagName") else "unknown"
                elem_id = target.id if hasattr(target, "id") else ""

                unit_id = target.getAttribute("data-unit")
                if unit_id and unit_id != jsnull:
                    break
            except Exception as e:
                HANDLER_LOGGER.error(f"[Handler] Error at depth {depth}: {e}")

            target = target.parentElement
            depth += 1

        if unit_id == jsnull:
            unit_id = None
        return target, unit_id

    def _handle_event(self, event) -> None:
        # Get coordinates relative to the viewport
        # Don't use getBoundingClientRect on transformed elements
        rect = self._owner.getBoundingClientRect()
        
        # Raw screen coordinates relative to container
        raw_x = event.clientX - rect.left
        raw_y = event.clientY - rect.top
        
        # For transformed coordinate calculations, we need to account for
        # the fact that the container itself might have transforms
        x = raw_x
        y = raw_y
        
        # Apply inverse transform to get coordinates in map space for hex calculations
        if self._map:
            # Inverse transform: (x - pan_x) / zoom
            x = (x - self._map._pan_x) / self._map._zoom_level
            y = (y - self._map._pan_y) / self._map._zoom_level
            
            HANDLER_LOGGER.debug(
                f"Transform: raw=({raw_x:.1f},{raw_y:.1f}) -> map=({x:.1f},{y:.1f}) "
                f"[zoom={self._map._zoom_level:.2f}, pan=({self._map._pan_x:.1f},{self._map._pan_y:.1f})]"
            )
        
        # Canvas scaling factors (for canvas internal resolution vs display size)
        if hasattr(self._owner, "width"):
            sx = self._owner.width / rect.width
        else:
            sx = 1.0

        if hasattr(self._owner, "height"):
            sy = self._owner.height / rect.height
        else:
            sy = 1.0
        
        if sx != 1.0 or sy != 1.0:
            HANDLER_LOGGER.debug(
                f"Canvas scaling: sx={sx:.4f}, sy={sy:.4f}, "
                f"owner.width={self._owner.width if hasattr(self._owner, 'width') else 'N/A'}, "
                f"rect.width={rect.width:.1f}"
            )

        modifiers = Modifiers.from_event(event)
        target, unit_id = self._get_event_target(event)

        # Position for SVG (map space)
        position = (x, y)
        # Raw position for screen-space operations and drag preview
        raw_position = (raw_x, raw_y)
        
        # Hex calculation needs scaled coordinates for canvas-based layouts
        scaled_position = (x * sx, y * sy)
        hex_value = self._layout.pixel_to_hex(*scaled_position) if self._layout else None

        result = EventInfo(
            event=event,
            owner=self._owner,
            position=position,
            raw_position=raw_position,
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
