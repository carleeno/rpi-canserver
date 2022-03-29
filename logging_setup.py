import logging
import logging.config
from os import makedirs, path

import yaml

CONFIG_FILE = path.dirname(path.abspath(__file__)) + "/logging_config.yaml"

LEVEL_COLORS = {
    logging.DEBUG: "\033[34m",  # blue
    logging.INFO: "",  # nothing
    logging.WARNING: "\033[1;33m",  # yellow
    logging.ERROR: "\033[1;31m",  # light red
    logging.CRITICAL: "\033[31m",  # red
}

RESET = "\033[0m"


class FileFormatter(logging.Formatter):
    def format(self, record):
        format = f"[%(asctime)s] [%(levelname)s] %(filename)s:%(funcName)s:%(lineno)s - (%(name)s) %(message)s"
        formatter = logging.Formatter(format)
        return formatter.format(record)


class ConsoleFormatter(logging.Formatter):
    def format(self, record):
        color = LEVEL_COLORS.get(record.levelno)
        format = f"(%(name)s) {color}%(message)s{RESET}"
        formatter = logging.Formatter(format)
        return formatter.format(record)


def setup_logging(log_path: str = "logs/canserver.log") -> logging.Logger:
    """Call this to setup logging."""
    makedirs(path.dirname(log_path), exist_ok=True)
    with open(CONFIG_FILE) as log_config:
        config_yml = log_config.read()
    config_dict = yaml.safe_load(config_yml)
    config_dict["handlers"]["file"]["filename"] = log_path
    logging.config.dictConfig(config_dict)
