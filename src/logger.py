import json
import logging
from pathlib import Path

from tqdm import tqdm


class ColorFormatter(logging.Formatter):
    COLORS: dict[str, str] = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET: str = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            The formatted log record.
        """
        levelname: str = record.levelname
        if levelname in self.COLORS:
            color: str = self.COLORS[levelname]
            record.levelname = f"{color}{levelname}{self.RESET}"
        return super().format(record)


class TqdmStreamHandler(logging.StreamHandler):
    """
    Console handler that writes through tqdm, so a log line is not glued to the progress bar line.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Write the log record above the progress bar.

        Args:
            record (logging.LogRecord): The log record to write.
        """
        try:
            tqdm.write(self.format(record), file=self.stream)
        except Exception:
            self.handleError(record)


def get_logger(name: str = "app_logger") -> logging.Logger:
    """
    Creates or returns already created logger.

    Args:
        name (str): Name of logger

    Returns:
        Logger.
    """
    logger: logging.Logger = logging.getLogger(name)

    if not logger.handlers:
        # Tracks any logger level from code
        logger.setLevel(logging.DEBUG)

        # Console handler
        console_handler: logging.StreamHandler = TqdmStreamHandler()
        # To console only prints INFO and above; for debugging set logging.DEBUG here (also saves debug files)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(ColorFormatter("[%(levelname)s] %(message)s"))
        logger.addHandler(console_handler)

        # Libraries that configure the root logger must not print our lines a second time
        logger.propagate = False

    return logger


def set_console_level(level: int) -> None:
    """
    Sets the console level for the logger.

    Args:
        level (int): The level to set the console to.
    """
    for handler in get_logger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setLevel(level)


def is_debug() -> bool:
    """
    Check whether debugging is on (console handler level set to DEBUG in get_logger).

    Returns:
        True when debugging is on.
    """
    return any(handler.level <= logging.DEBUG for handler in get_logger().handlers)


def save_debug_json(file_name: str, data: dict) -> None:
    """
    Save data as JSON into the working folder when debugging is on.

    Args:
        file_name (str): Name of the file in the working folder.
        data (dict): Data to save.
    """
    if not is_debug():
        return
    path: Path = Path.cwd().joinpath(file_name)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
    get_logger().debug(f"Debug file saved: {path.as_posix()}")
