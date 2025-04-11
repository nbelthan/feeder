import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Ensure log directory exists
os.makedirs("logs", exist_ok=True)

# Set up logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEBUG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s"

# Configure root logger
def configure_logging(debug_mode=True):
    """
    Configure logging for the application.
    
    Args:
        debug_mode: If True, sets higher verbosity for debugging
    """
    log_level = logging.DEBUG # Force DEBUG level for now
    # Create formatters
    console_formatter = logging.Formatter(DEBUG_FORMAT if log_level == logging.DEBUG else LOG_FORMAT, DATE_FORMAT)
    file_formatter = logging.Formatter(DEBUG_FORMAT, DATE_FORMAT)
    
    # Create handlers
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler = RotatingFileHandler(
        "logs/feeder.log", 
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    
    # Set log levels
    console_handler.setLevel(log_level) # Use forced level
    file_handler.setLevel(log_level) # Use forced level
    
    # Set formatters
    console_handler.setFormatter(console_formatter)
    file_handler.setFormatter(file_formatter)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level) # Use forced level
    
    # Remove any existing handlers to avoid duplicate logs
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Create a separate error log file
    error_handler = RotatingFileHandler(
        "logs/error.log",
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # Set OpenAI logger to INFO level for debugging
    openai_logger = logging.getLogger("openai")
    openai_logger.setLevel(logging.INFO if debug_mode else logging.WARNING)
    
    # Log startup message
    logging.info("Logging configured with debug_mode=%s", debug_mode) 