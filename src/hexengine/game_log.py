"""
Per-request game logger: stdlib logging plus optional fan-out to WebSocket clients.

Install a :class:`GameLogger` for the duration of :meth:`hexengine.server.game_server.GameServer.handle_message`
via :func:`game_logger_scope`; game code calls :func:`get_game_logger` to log once to server stdout and
(inside that scope) enqueue the same line for ``\"server_log\"`` broadcasts.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Final

MAX_CLIENT_GAME_LOG_CHARS: Final[int] = 4096

_game_logger_ctx: ContextVar[GameLogger | None] = ContextVar(
    "hexengine_game_logger", default=None
)


def _cap_message(msg: str) -> str:
    s = msg.replace("\r\n", "\n").replace("\r", "\n")
    first_line = s.split("\n", 1)[0]
    if len(first_line) > MAX_CLIENT_GAME_LOG_CHARS:
        return first_line[: MAX_CLIENT_GAME_LOG_CHARS - 20] + "…(truncated)"
    return first_line


def _wire_text(msg: object, *args: object) -> str:
    if isinstance(msg, str) and args:
        try:
            return msg % args
        except (TypeError, ValueError):
            pass
    return str(msg)


class GameLogger:
    """Logs to a stdlib :class:`logging.Logger` and optionally enqueues wire-safe lines."""

    __slots__ = ("_enqueue", "_stdlib")

    def __init__(
        self,
        *,
        logger_name: str,
        enqueue_client: Callable[[str, str, str], None] | None,
    ) -> None:
        self._stdlib = logging.getLogger(logger_name)
        self._enqueue = enqueue_client

    def debug(self, msg: object, *args: object, **_kwargs: Any) -> None:
        self._stdlib.debug(msg, *args, **_kwargs)
        if self._enqueue is not None:
            self._enqueue(
                "DEBUG", self._stdlib.name, _cap_message(_wire_text(msg, *args))
            )

    def info(self, msg: object, *args: object, **_kwargs: Any) -> None:
        self._stdlib.info(msg, *args, **_kwargs)
        if self._enqueue is not None:
            self._enqueue(
                "INFO", self._stdlib.name, _cap_message(_wire_text(msg, *args))
            )

    def warning(self, msg: object, *args: object, **_kwargs: Any) -> None:
        self._stdlib.warning(msg, *args, **_kwargs)
        if self._enqueue is not None:
            self._enqueue(
                "WARNING", self._stdlib.name, _cap_message(_wire_text(msg, *args))
            )

    def error(self, msg: object, *args: object, **_kwargs: Any) -> None:
        self._stdlib.error(msg, *args, **_kwargs)
        if self._enqueue is not None:
            self._enqueue(
                "ERROR", self._stdlib.name, _cap_message(_wire_text(msg, *args))
            )

    def critical(self, msg: object, *args: object, **_kwargs: Any) -> None:
        self._stdlib.critical(msg, *args, **_kwargs)
        if self._enqueue is not None:
            self._enqueue(
                "CRITICAL", self._stdlib.name, _cap_message(_wire_text(msg, *args))
            )


_FALLBACK = GameLogger(logger_name="hexengine.game", enqueue_client=None)


def get_game_logger() -> GameLogger:
    """Return the active per-request logger, or a stdlib-only fallback when unset."""
    g = _game_logger_ctx.get()
    return g if g is not None else _FALLBACK


@contextmanager
def game_logger_scope(logger: GameLogger) -> Iterator[None]:
    """Bind ``logger`` for :func:`get_game_logger` within the context block."""
    token = _game_logger_ctx.set(logger)
    try:
        yield
    finally:
        _game_logger_ctx.reset(token)
