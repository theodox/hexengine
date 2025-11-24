import logging
import js                               # pyright: ignore[reportMissingImports]
from .document import element

from pyodide.ffi import create_proxy     # pyright: ignore[reportMissingImports]

"""
A development console that logs messages to a text area in the web page, using
standard Python logging idioms
"""

ROOT_LOGGER = None

__version__ = "0.1.0"

def initialize(name: str, game_globals) -> logging.Logger:
    
    textArea = element("console")
    assert textArea is not None, "Console text area not found"
    inputArea = element("console-input")
    assert inputArea is not None, "Console input area not found"
    log_level_select = element("log-level-picker")
    assert log_level_select is not None, "Log level picker not found"

    global ROOT_LOGGER
    ROOT_LOGGER = logging.getLogger(name)
    handler = DevLogHandler(textArea)
    handler.setFormatter(logging.Formatter(" {message}", style="{"))
    ROOT_LOGGER.addHandler(handler)
    ROOT_LOGGER.setLevel(logging.DEBUG)

    # We need a reference the writer to update the log display later
    TextAreaWriter.INSTANCE = handler.writer

    # Set up the log level selector
    log_level_select.addEventListener(
        "change",
        create_proxy(
            lambda event: update_log_display(event, textArea)
        ),
    )

    TextAreaReader.INSTANCE = TextAreaReader(inputArea, game_globals)
    ROOT_LOGGER.debug("Dev console initialized")


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
        self.textArea.scrollTop = self.textArea.scrollHeight

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

class TextAreaReader:
    INSTANCE = None

    def __init__(self, textArea: js.HTMLElement, game_globals:dict):
        self.textArea = textArea    
        self.game_globals = game_globals
        self.textArea.addEventListener(
            "keyup",
            create_proxy(self.on_keyup)
            )
        self.logger = logging.getLogger("input")
        self.logger.debug("TextAreaReader initialized")
        self.history = []
        self.history_index = -1

    def on_keyup(self, event):

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
    def __init__(self, textArea: js.HTMLElement):
        # this is always "NOTSET" because filtering is done in TextAreaWriter
        super().__init__(logging.NOTSET)
        self.writer = TextAreaWriter(textArea)

    def emit(self, record: logging.LogRecord) -> None:
        log_entry = self.format(record)
        self.writer.write(record.levelno, log_entry)
