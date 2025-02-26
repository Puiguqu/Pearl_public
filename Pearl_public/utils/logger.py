import logging
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
from colorama import init, Fore

# Initialize colorama for Windows
init()

# Constants
LOG_FILE = "assistant.log"
LOG_LEVEL = logging.DEBUG
MAX_BYTES = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 5

# Configure logger
logger = logging.getLogger("AssistantLogger")
logger.setLevel(LOG_LEVEL)

# File handler with rotation
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=MAX_BYTES,
    backupCount=BACKUP_COUNT,
    encoding='utf-8'
)

# Create formatters
file_formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

console_formatter = logging.Formatter(
    f"{Fore.CYAN}%(asctime)s{Fore.RESET} - "
    f"{Fore.GREEN}%(levelname)s{Fore.RESET} - "
    f"%(message)s",
    datefmt="%H:%M:%S"
)

# Apply formatters
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

def log_error(message):
    """Log error with red color."""
    logger.error(f"{Fore.RED}{message}{Fore.RESET}")

def log_warning(message):
    """Log warning with yellow color."""
    logger.warning(f"{Fore.YELLOW}{message}{Fore.RESET}")

def log_info(message):
    """Log info with default color."""
    logger.info(message)

def log_debug(message):
    """Log debug with gray color."""
    logger.debug(f"{Fore.LIGHTBLACK_EX}{message}{Fore.RESET}")

def log_success(message):
    """Log success with green color."""
    logger.info(f"{Fore.GREEN}✓ {message}{Fore.RESET}")

def log_json(data):
    """Log JSON data with formatting."""
    logger.info(f"\n{json.dumps(data, indent=2)}")

# Example usage
if __name__ == "__main__":
    log_info("This is an info message.")
    log_warning("This is a warning message.")
    log_error("This is an error message.")
    log_critical("This is a critical message.")
