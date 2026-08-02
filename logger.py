import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import config

MAX_BYTES = 10 * 1024 * 1024  # 10 MB limit per log file
BACKUP_COUNT = 5              # Maintain up to 5 rotated backup log files

def get_logger(name: str, log_file_path: str, level=logging.INFO) -> logging.Logger:
    """
    Creates and returns a thread-safe, auto-rotating logger.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(level)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s] - %(message)s')

        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

        # Rotating File Handler
        file_handler = RotatingFileHandler(
            log_file_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

        # Console Stream Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)

    return logger

# Instantiate dedicated production loggers
server_logger = get_logger('server', config.SERVER_LOG_PATH)
recognition_logger = get_logger('recognition', config.RECOGNITION_LOG_PATH)
training_logger = get_logger('training', config.TRAINING_LOG_PATH)
attendance_logger = get_logger('attendance', config.ATTENDANCE_LOG_PATH)
error_logger = get_logger('errors', config.ERRORS_LOG_PATH, level=logging.ERROR)
