"""
Centralized logging configuration for SunCheck bot.
Provides structured logging with timestamps and log levels.
"""
import logging
import sys
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional


# Log format constants
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_bytes: int = 5_000_000,  # 5MB
    backup_count: int = 3
) -> logging.Logger:
    """
    Configure and return the root logger for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, logs only to console.
        max_bytes: Maximum size of log file before rotation.
        backup_count: Number of backup files to keep.
    
    Returns:
        Configured root logger.
    """
    # Get numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create root logger
    root_logger = logging.getLogger("suncheck")
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, DATE_FORMAT))
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
        root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Args:
        name: Module name (typically __name__)
    
    Returns:
        Logger instance for the module.
    """
    return logging.getLogger(f"suncheck.{name}")


class BotLogger:
    """
    In-memory logger that also maintains a list of recent log entries
    for the dashboard UI. Wraps the standard logging module.
    """
    
    def __init__(self, name: str = "bot", max_entries: int = 100):
        self.logger = get_logger(name)
        self.max_entries = max_entries
        self.entries: list[str] = []
    
    def _add_entry(self, level: str, message: str) -> str:
        """Add entry to in-memory list and return formatted string."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}"
        self.entries.insert(0, entry)  # Prepend for newest first
        if len(self.entries) > self.max_entries:
            self.entries.pop()
        return entry
    
    def debug(self, message: str) -> None:
        """Log debug message."""
        self._add_entry("DEBUG", message)
        self.logger.debug(message)
    
    def info(self, message: str) -> None:
        """Log info message."""
        self._add_entry("INFO", message)
        self.logger.info(message)
    
    def warning(self, message: str) -> None:
        """Log warning message."""
        self._add_entry("WARN", message)
        self.logger.warning(message)
    
    def error(self, message: str) -> None:
        """Log error message."""
        self._add_entry("ERROR", message)
        self.logger.error(message)
    
    def critical(self, message: str) -> None:
        """Log critical message."""
        self._add_entry("CRIT", message)
        self.logger.critical(message)
    
    def opportunity(self, message: str) -> None:
        """Log trading opportunity (special marker)."""
        self._add_entry("OPPORTUNITY", message)
        self.logger.info(f"!!! OPPORTUNITY: {message}")
    
    def trade(self, message: str) -> None:
        """Log trade execution (special marker)."""
        self._add_entry("TRADE", message)
        self.logger.info(f">>> TRADE: {message}")
    
    def get_entries(self) -> list[str]:
        """Get list of recent log entries for UI."""
        return self.entries.copy()
    
    def clear(self) -> None:
        """Clear in-memory log entries."""
        self.entries.clear()


# Initialize default logging on module import
_default_logger = None


def init_default_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Initialize default logging configuration. Call once at app startup."""
    global _default_logger
    _default_logger = setup_logging(level=level, log_file=log_file)
    return _default_logger
