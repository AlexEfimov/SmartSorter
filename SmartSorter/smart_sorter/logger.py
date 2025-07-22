# logger.py — Настройка логирования в файл и консоль

import logging
from pathlib import Path


def setup_logging(log_file: Path) -> logging.Logger:
    logger = logging.getLogger("smart_sorter")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
