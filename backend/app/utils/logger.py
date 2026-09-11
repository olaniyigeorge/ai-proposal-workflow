import logging
import sys
import os

# Ensure the logs directory exists
os.makedirs("logs", exist_ok=True)

# Ensure the server.logs file exists
log_file_path = "logs/server.logs"
if not os.path.exists(log_file_path):
    with open(log_file_path, "w"):
        pass

# Configure logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(fmt="%(asctime)s - %(levelname)s - %(message)s")

# Create and configure stream handler
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)

# # Create and configure file handler
file_handler = logging.FileHandler(log_file_path)
file_handler.setFormatter(formatter)

# # Add handlers to logger
logger.handlers = [
    stream_handler,
]  # file_handler

# SQLAlchemy's "sqlalchemy.engine" logger propagates into this root logger by
# default, printing every SQL statement a second time (once via SQLAlchemy's
# own logging, once via this module's handler) whenever engine echo is on —
# and even with echo off, leaving this logger at its default level can still
# be noisy. Keep it quiet unless someone explicitly wants SQL_ECHO=true, in
# which case core/database.py's own `echo=True` on the engine is the
# intended (single) source of that output, not this logger.
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").propagate = False
