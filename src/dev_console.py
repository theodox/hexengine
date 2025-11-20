import logging
import js  # pyright: ignore[reportMissingImports]

from pyodide.ffi import create_proxy # pyright: ignore[reportMissingImports]

"""
A development console that logs messages to a text area in the web page, using
standard Python logging idioms
"""

ROOT_LOGGER = None

__version__ = "0.1.0"

def initialize(name: str, textArea: js.HTMLElement) -> logging.Logger:
    global ROOT_LOGGER
    ROOT_LOGGER = logging.getLogger(name)
    handler = DevLogHandler(textArea)
    handler.setFormatter(logging.Formatter("{levelname} - {message}", style="{"))
    ROOT_LOGGER.addHandler(handler)
    ROOT_LOGGER.setLevel(logging.DEBUG)

    # We need a reference the writer to update the log display later
    TextAreaWriter.INSTANCE = handler.writer

    # Set up the log level selector
    log_level_select = js.document.getElementById("log-level-picker")
    log_level_select.addEventListener(
        "change",
        create_proxy(
            lambda event: update_log_display(
                event, js.document.getElementById("console")
            )
        ),
    )


def update_log_display(event, textArea: js.HTMLElement):
    level_str = event.target.value
    level = getattr(logging, level_str.upper(), logging.DEBUG)
    TextAreaWriter.set_active_level(level)
    TextAreaWriter.update(level)


class TextAreaWriter:
    ACTIVE_LEVEL = logging.DEBUG
    INSTANCE = None

    def __init__(self, textArea: js.HTMLElement):
        self.textArea = textArea
        self.items = [(50, __version__)]

    def write(self, level: int, message: str):
        self.items.append((level, message))
        if level >= self.ACTIVE_LEVEL:
            self.textArea.value += message + "\n"

    def flush(self):
        pass

    @classmethod
    def set_active_level(cls, level: int):
        cls.ACTIVE_LEVEL = level

    @classmethod
    def update(cls, level: int):
        slf = cls.INSTANCE
        js.console.log(slf)
        messages = [msg for lvl, msg in slf.items if lvl >= level]
        slf.textArea.value = "\n".join(messages or ["-"])
        slf.textArea.scrollTop = slf.textArea.scrollHeight


class DevLogHandler(logging.Handler):
    def __init__(self, textArea: js.HTMLElement):
        # this is always "NOTSET" because filtering is done in TextAreaWriter
        super().__init__(logging.NOTSET)
        self.writer = TextAreaWriter(textArea)

    def emit(self, record: logging.LogRecord) -> None:
        log_entry = self.format(record)
        self.writer.write(record.levelno, log_entry)
