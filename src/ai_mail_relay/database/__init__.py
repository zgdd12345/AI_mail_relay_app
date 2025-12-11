"""Database layer for AI Mail Relay."""

from .connection import get_connection, init_database, close_connection
from .migrations import run_migrations, get_current_version

__all__ = [
    "get_connection",
    "init_database",
    "close_connection",
    "run_migrations",
    "get_current_version",
]
