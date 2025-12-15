import logging
from typing import Callable, Dict, List


class EventBus:
    """
    Central event bus for decoupled communication between game components.
    
    Usage:
        bus = EventBus()
        bus.subscribe('unit_clicked', handler_func)
        bus.emit('unit_clicked', unit=unit_obj, position=(10, 20))
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self.logger = logging.getLogger("event_bus")
    
    def subscribe(self, event_name: str, handler: Callable) -> None:
        """Subscribe a handler to an event."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        self._subscribers[event_name].append(handler)
        self.logger.debug(f"Subscribed {handler.__name__} to '{event_name}'")
    
    def unsubscribe(self, event_name: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event."""
        if event_name in self._subscribers:
            try:
                self._subscribers[event_name].remove(handler)
                self.logger.debug(f"Unsubscribed {handler.__name__} from '{event_name}'")
            except ValueError:
                pass
    
    def emit(self, event_name: str, **kwargs) -> None:
        """Emit an event with keyword arguments."""
        if event_name in self._subscribers:
            self.logger.debug(f"Emitting '{event_name}' to {len(self._subscribers[event_name])} subscribers")
            for handler in self._subscribers[event_name]:
                try:
                    handler(**kwargs)
                except Exception as e:
                    self.logger.error(f"Error in handler {handler.__name__} for event '{event_name}': {e}")
    
    def clear(self, event_name: str = None) -> None:
        """Clear all subscribers for an event, or all events if event_name is None."""
        if event_name is None:
            self._subscribers.clear()
        elif event_name in self._subscribers:
            self._subscribers[event_name].clear()


class GameEventHandler:
    """
    Event handler for game events on an owner element.
    """

    def __init__(self):
        self._handlers = []
            
    def _handle_event(self, *args, **kwargs):
        
        for handler in self._handlers:
            handler(*args, **kwargs)

    def __lt__(self, handler):
        # use < to add a handler
        logging.getLogger().debug(f"Adding handler {handler} to {self}")
        return self

    def __isub__(self, handler):
        for h in self._handlers:
            if h == handler:
                self._handlers.remove(h)
                break
            
    def __repr__(self):
        return f"<GameEventHandler event_type={self._event_type} owner={self._owner}>"