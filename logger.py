import logging
from logging.handlers import RotatingFileHandler
import os

# Create logs directory if not exists
os.makedirs("logs", exist_ok=True)

# Logger config
logger = logging.getLogger("autometa_logger")
logger.setLevel(logging.DEBUG)

# File handler: logs/debug.log (rotating files)
file_handler = RotatingFileHandler("logs/debug.log", maxBytes=1_000_000, backupCount=3)
file_formatter = logging.Formatter(
    "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
)
file_handler.setFormatter(file_formatter)

# Console handler (stream)
console_handler = logging.StreamHandler()
console_handler.setFormatter(file_formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)
