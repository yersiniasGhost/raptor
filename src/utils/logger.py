import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from .singleton import Singleton
from typing import Dict
from .envvars import EnvVars


class LogManager(metaclass=Singleton):

    def __init__(self, log_filename: str = "raptor.log"):
        self._loggers: Dict[str, logging.Logger] = {}
        self._file_handler = None
        self._setup_base_config(log_filename)


    def _setup_base_config(self, log_filename: str):
        """Initialize base logging configuration."""
        log_dir = Path('/var/log/raptor')
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            print("Warning: Cannot create /var/log/raptor. Ensure proper permissions.")
            # Fallback to current directory
            log_dir = Path('.')

        if self._file_handler is None:
            self._file_handler = RotatingFileHandler(
                log_dir / log_filename,
                maxBytes=10485760,  # 10MB
                backupCount=5
            )

            # Detailed formatter with module name
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]'
            )
            self._file_handler.setFormatter(formatter)
        # # Create formatters
        # self.detailed_formatter = logging.Formatter(
        #     '%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]'
        # )
        # self.simple_formatter = logging.Formatter(
        #     '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        # )



    def get_logger(self, name: str) -> logging.Logger:
        if name not in self._loggers:
            logger = logging.getLogger(name)
            logger.setLevel(EnvVars().log_level)

            # Remove any existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

            # Add our single file handler
            logger.addHandler(self._file_handler)

            # Prevent propagation to root logger
            logger.propagate = False

            self._loggers[name] = logger

        return self._loggers[name]


    def update_all_log_levels(self, level: int):
        """Update log level for all managed loggers."""
        for logger in self._loggers.values():
            logger.setLevel(level)

    def get_all_loggers(self) -> Dict[str, logging.Logger]:
        """Get dictionary of all managed loggers."""
        return self._loggers.copy()
