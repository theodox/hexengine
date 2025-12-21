import sys
import logging


def except_hook(exc_type, exc_value, exc_traceback):
    """Custom exception hook to log uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Call the default excepthook for KeyboardInterrupt
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    else:
        logger = logging.getLogger()
        logger.error(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )


def install_exception_hook(logger: logging.Logger = None):
    """Install the custom exception hook."""
    sys.excepthook = except_hook
    if logger is not None:
        logging.getLogger().debug("Custom exception hook installed.")
