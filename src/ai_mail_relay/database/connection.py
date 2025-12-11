"""SQLite connection management with WAL mode for better concurrency."""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import DatabaseConfig

logger = logging.getLogger(__name__)

# Thread-local storage for connections
_local = threading.local()
_db_path: Path | None = None


def _ensure_db_directory(path: Path) -> None:
    """Ensure the database directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _configure_connection(conn: sqlite3.Connection) -> None:
    """Configure SQLite connection for optimal performance."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")


def init_database(config: DatabaseConfig) -> None:
    """Initialize the database with the given configuration.

    This must be called before any database operations.
    Creates the database directory if it doesn't exist.
    """
    global _db_path
    _db_path = Path(config.path)
    _ensure_db_directory(_db_path)
    logger.info("Database initialized at: %s", _db_path)


def get_connection() -> sqlite3.Connection:
    """Get a thread-local database connection.

    Returns the existing connection for this thread, or creates a new one.
    Connections are configured with WAL mode and foreign keys enabled.

    Raises:
        RuntimeError: If init_database() hasn't been called.
    """
    if _db_path is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    if not hasattr(_local, "connection") or _local.connection is None:
        _local.connection = sqlite3.connect(str(_db_path))
        _configure_connection(_local.connection)
        logger.debug("Created new database connection for thread %s", threading.current_thread().name)

    return _local.connection


def close_connection() -> None:
    """Close the database connection for the current thread."""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None
        logger.debug("Closed database connection for thread %s", threading.current_thread().name)


def get_db_path() -> Path | None:
    """Get the current database path, or None if not initialized."""
    return _db_path
