import logging
import js
from pyodide.ffi import create_proxy


LEVELS = {
    'NOTSET': 0,
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50
}


def create_Logger(name: str, textArea: "TextArea") -> logging.Logger:
    logger = logging.getLogger(name)
    handler = DevLogHandler(textArea)
    handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    initialize_log_picker()
    return logger

def initialize_log_picker():
    log_level_select = js.document.getElementById("console_level_picker")
    log_level_select.addEventListener(
        "change", 
        create_proxy(lambda event: handle_level_select(event, js.document.getElementById("console_output")))
        )
    
                                      
def handle_level_select(event, textArea: "TextArea"):
    level_str = event.target.value
    level = getattr(logging, level_str.upper(), logging.DEBUG)
    TextAreaWriter.set_active_level(level)
    TextAreaWriter.update(level)

class TextAreaWriter:

    ACTIVE_LEVEL = logging.DEBUG
    INSTANCE = None

    def __init__(self, textArea: "TextArea"):
        self.textArea = textArea
        self.items = []
        
    def write(self, level: int,message: str):
        self.items.append((level, message))
        if level >= self.ACTIVE_LEVEL:
            self.textArea.value += "\n" + message
        
                  
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

    def __init__(self, textArea: "TextArea"):
        # this is always "NOTSET" because filtering is done in TextAreaWriter
        super().__init__(logging.NOTSET) 
        self.writer = TextAreaWriter(textArea)
        TextAreaWriter.INSTANCE = self.writer


    def emit(self, record):
        log_entry = self.format(record)
        self.writer.write(record.levelno, log_entry)
        