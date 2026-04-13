from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .document import create_proxy, element, js

"""
A development console that logs messages to a text area in the web page, using
standard Python logging idioms
"""

ROOT_LOGGER = None

try:
    __version__ = version("hexes")
except PackageNotFoundError:
    __version__ = "0.1.3"


def initialize(name: str, game_globals: dict[str, Any]) -> logging.Logger:
    textArea = element("console")
    assert textArea is not None, "Console text area not found"
    inputArea = element("console-input")
    assert inputArea is not None, "Console input area not found"
    log_level_select = element("log-level-picker")
    assert log_level_select is not None, "Log level picker not found"

    status_line = element("status-line")
    assert status_line is not None, "Status line area not found"
    StatusLine.INSTANCE = StatusLine(status_line)

    global ROOT_LOGGER
    ROOT_LOGGER = logging.getLogger(name)
    handler = DevLogHandler(textArea)
    handler.setFormatter(logging.Formatter("{name} | {message}", style="{"))
    ROOT_LOGGER.addHandler(handler)
    ROOT_LOGGER.setLevel(logging.DEBUG)

    # We need a reference the writer to update the log display later
    TextAreaWriter.INSTANCE = handler.writer

    # Set up the log level selector
    log_level_select.addEventListener(
        "change",
        create_proxy(lambda event: update_log_display(event, textArea)),
    )

    TextAreaReader.INSTANCE = TextAreaReader(inputArea, game_globals)
    ROOT_LOGGER.info("Dev console initialized")
    TextAreaWriter.set_active_level(logging.INFO)
    TextAreaWriter.update(logging.INFO)


def update_log_display(event, textArea: js.HTMLElement) -> None:
    level_str = event.target.value
    level = getattr(logging, level_str.upper(), logging.DEBUG)
    TextAreaWriter.set_active_level(level)
    TextAreaWriter.update(level)


def set_status(message: str) -> None:
    """
    Update the dev status line (`#status-line`).

    Safe to call before `initialize` or if the DOM is unavailable (no-op).
    """
    try:
        inst = StatusLine.INSTANCE
        if inst is None:
            return
        inst.set_status(message)
    except Exception:
        pass


class TextAreaWriter:
    ACTIVE_LEVEL = logging.DEBUG
    INSTANCE = None

    def __init__(self, textArea: js.HTMLElement) -> None:
        self.textArea = textArea
        self.items = [(50, __version__)]

    def write(self, level: int, message: str) -> None:
        self.items.append((level, message))
        if level >= self.ACTIVE_LEVEL:
            self.textArea.value += message + "\n"
        self.textArea.scrollTop = self.textArea.scrollHeight

    def flush(self) -> None:
        pass

    @classmethod
    def set_active_level(cls, level: int) -> None:
        cls.ACTIVE_LEVEL = level

    @classmethod
    def update(cls, level: int) -> None:
        slf = cls.INSTANCE
        js.console.log(slf)
        messages = [msg for lvl, msg in slf.items if lvl >= level]
        slf.textArea.value = "\n".join(messages or ["-"])
        slf.textArea.scrollTop = slf.textArea.scrollHeight


class StatusLine:
    INSTANCE = None

    def __init__(self, textArea: js.HTMLElement) -> None:
        self.textArea = textArea
        self.logger = logging.getLogger("status")
        self.logger.debug("StatusLine initialized")

    def set_status(self, message: str) -> None:
        self.textArea.value = message


class TextAreaReader:
    INSTANCE = None

    def __init__(self, textArea: js.HTMLElement, game_globals: dict[str, Any]) -> None:
        self.textArea = textArea
        self.game_globals = game_globals
        self.textArea.addEventListener("keyup", create_proxy(self.on_keyup))
        self.logger = logging.getLogger("input")
        self.logger.debug("TextAreaReader initialized")
        self.history = []
        self.history_index = -1

    def on_keyup(self, event) -> None:
        if event.key == "ArrowUp":
            if self.history:
                self.history_index = max(0, self.history_index - 1)
                self.textArea.value = self.history[self.history_index]
            return
        elif event.key == "ArrowDown":
            if self.history:
                self.history_index = min(len(self.history) - 1, self.history_index + 1)
                self.textArea.value = self.history[self.history_index]
            return

        if event.key != "Enter":
            return

        self.history.append(self.textArea.value.strip())
        self.history_index = len(self.history)
        self.logger.debug(f"> {self.textArea.value.strip()}")
        try:
            self.logger.debug(
                ("> " + str(eval(self.textArea.value, self.game_globals))).strip()
            )
        except Exception as e:
            self.logger.error(f"Error executing input: {e}")

        self.textArea.value = ""


class DevLogHandler(logging.Handler):
    def __init__(self, textArea: js.HTMLElement) -> None:
        # this is always "NOTSET" because filtering is done in TextAreaWriter
        super().__init__(logging.NOTSET)
        self.writer = TextAreaWriter(textArea)

    def emit(self, record: logging.LogRecord) -> None:
        log_entry = self.format(record)
        self.writer.write(record.levelno, log_entry)
