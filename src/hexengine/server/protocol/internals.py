"""
Internal wire protocol machinery.

Public protocol surface should generally be imported from
`hexengine.server.protocol` (the package `__init__.py` re-exports).
"""

from __future__ import annotations

import json
from dataclasses import MISSING, asdict, dataclass, fields
from typing import Any, Literal, TypeVar, cast

_WirePayloadT = TypeVar("_WirePayloadT")


WireMessageType = str
MessageDirection = Literal["client_to_server", "server_to_client"]

_WIRE_MESSAGE_REGISTRY: dict[WireMessageType, type[Any]] = {}
_WIRE_MESSAGE_DIRECTION: dict[WireMessageType, MessageDirection] = {}


def _wire_message(
    direction: MessageDirection,
    message_type: WireMessageType,
    *,
    omit_if_none: frozenset[str] | None = None,
) -> Any:

    def decorator(cls: type[_WirePayloadT]) -> type[_WirePayloadT]:
        if message_type in _WIRE_MESSAGE_REGISTRY:
            raise ValueError(
                f"wire_message: duplicate registration for {message_type!r} "
                f"({_WIRE_MESSAGE_REGISTRY[message_type].__name__} vs {cls.__name__})"
            )
        _WIRE_MESSAGE_REGISTRY[message_type] = cls
        _WIRE_MESSAGE_DIRECTION[message_type] = direction
        cls.wire_type = message_type  # type: ignore[attr-defined]
        cls.wire_direction = direction  # type: ignore[attr-defined]

        cls_dict = cls.__dict__
        if "to_message" not in cls_dict:
            o = omit_if_none

            def to_message(self: Any) -> Message:
                fs = fields(cls)
                if not fs:
                    return Message(type=message_type, payload={})
                d = asdict(self)
                if o:
                    d = {k: v for k, v in d.items() if not (k in o and v is None)}
                return Message(type=message_type, payload=d)

            cls.to_message = to_message  # type: ignore[attr-defined]

        if "from_message" not in cls_dict:

            @classmethod
            def from_message(cls_: type[Any], msg: Message) -> Any:
                return _wire_from_message(cls_, msg.payload)

            cls.from_message = from_message  # type: ignore[attr-defined]

        return cls

    return decorator


def client_message(
    message_type: WireMessageType,
    *,
    omit_if_none: frozenset[str] | None = None,
) -> Any:
    """Register a client -> server payload dataclass for a wire type string."""
    return _wire_message("client_to_server", message_type, omit_if_none=omit_if_none)


def server_message(
    message_type: WireMessageType,
    *,
    omit_if_none: frozenset[str] | None = None,
) -> Any:
    """Register a server -> client payload dataclass for a wire type string."""
    return _wire_message("server_to_client", message_type, omit_if_none=omit_if_none)


def _wire_from_message(cls: type[Any], p: dict[str, Any]) -> Any:
    fs = fields(cls)
    if not fs:
        return cls()
    kwargs: dict[str, Any] = {}
    for f in fs:
        if f.name in p:
            kwargs[f.name] = p[f.name]
        elif f.default is not MISSING:
            kwargs[f.name] = f.default
        elif f.default_factory is not MISSING:
            kwargs[f.name] = f.default_factory()
        else:
            raise KeyError(
                f"Wire payload missing required field {f.name!r} for {cls.__name__}"
            )
    return cls(**kwargs)


def registered_message_types() -> frozenset[WireMessageType]:
    """All wire message type values that have a registered payload class."""
    return frozenset(_WIRE_MESSAGE_REGISTRY.keys())


def registered_client_message_types() -> frozenset[WireMessageType]:
    return frozenset(
        t for t, d in _WIRE_MESSAGE_DIRECTION.items() if d == "client_to_server"
    )


def registered_server_message_types() -> frozenset[WireMessageType]:
    return frozenset(
        t for t, d in _WIRE_MESSAGE_DIRECTION.items() if d == "server_to_client"
    )


def assert_wire_registry_covers_message_types() -> None:
    # With enums removed, treat "coverage" as:
    # - every registered wire type has a direction
    # - no empty registry after import side-effects
    missing_dir = [t for t in _WIRE_MESSAGE_REGISTRY if t not in _WIRE_MESSAGE_DIRECTION]
    if missing_dir:
        raise RuntimeError(
            "wire_message registry missing direction for: " + ", ".join(missing_dir)
        )
    if not _WIRE_MESSAGE_REGISTRY:
        raise RuntimeError("wire_message registry is empty (protocol modules not imported?)")


@dataclass
class Message:
    """Base wire message structure."""

    type: WireMessageType
    payload: dict[str, Any]

    def to_json(self) -> str:
        """Serialize message to JSON."""
        return json.dumps({"type": self.type, "payload": self.payload})

    @classmethod
    def from_json(cls, data: str) -> Message:
        """Deserialize message from JSON."""
        obj = json.loads(data)
        return cls(type=cast(str, obj["type"]), payload=obj["payload"])

    @classmethod
    def try_from_json(cls, data: str) -> Message | None:
        """
        Deserialize JSON; return None if "type" is missing or not a known
        wire message type (forward-compatible with newer servers).
        """
        obj = json.loads(data)
        t = obj.get("type")
        if not isinstance(t, str):
            return None
        if t not in _WIRE_MESSAGE_REGISTRY:
            return None
        p = obj.get("payload")
        if not isinstance(p, dict):
            p = {}
        return cls(type=t, payload=p)

