import logging
from pyodide.ffi import create_proxy

HANDLER_LOGGER = logging.getLogger("handler")
HANDLER_LOGGER.setLevel(logging.DEBUG)


class Handler:
    """
    Event handler for UI events on an owner element.
    """

    def __init__(self, owner, event_type: str):
        self._handlers = []
        self._owner = owner
        self._event_type = event_type
        self.proxy = create_proxy(self._handle_event)
        self._owner.addEventListener(event_type, self.proxy)


    def _handle_event(self, event):
        # handle the click coordinates for canvas elements
        rect = event.target.getBoundingClientRect()
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

        for handler in self._handlers:
            handler(event, self._owner, (x * sx, y * sy))

    def __lt__(self, handler):
        # use < to add a handler
        logging.getLogger().debug(f"Adding handler {handler} to {self}")
        self._handlers.append(create_proxy(handler))
        return self

    def __isub__(self, handler):
        raise NotImplemented

    def __repr__(self):
        return f"<Handler event_type={self._event_type} owner={self._owner}>"
