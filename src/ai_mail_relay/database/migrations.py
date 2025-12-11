"""Database schema migrations for AI Mail Relay."""

from __future__ import annotations

import logging
from typing import Callable

from .connection import get_connection

logger = logging.getLogger(__name__)

# Migration functions: each takes a connection and applies schema changes
Migration = Callable[[], None]

MIGRATIONS: list[tuple[int, str, Migration]] = []


def migration(version: int, description: str):
    """Decorator to register a migration function."""
    def decorator(func: Migration) -> Migration:
        MIGRATIONS.append((version, description, func))
        return func
    return decorator


@migration(1, "Create papers table")
def migration_001_create_papers_table() -> None:
    """Create the papers table for storing arXiv papers."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            arxiv_id TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            authors TEXT NOT NULL,
            categories TEXT NOT NULL,
            abstract TEXT,
            links TEXT,
            affiliations TEXT,
            summary TEXT,
            research_field TEXT,
            published_date DATE,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);
        CREATE INDEX IF NOT EXISTS idx_papers_published_date ON papers(published_date);
        CREATE INDEX IF NOT EXISTS idx_papers_processed_at ON papers(processed_at);
    """)
    conn.commit()


@migration(2, "Create users and subscriptions tables")
def migration_002_create_users_tables() -> None:
    """Create user management tables."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            sub_type TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, sub_type, value)
        );

        CREATE TABLE IF NOT EXISTS delivery_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            paper_id INTEGER NOT NULL,
            delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
            UNIQUE(user_id, paper_id)
        );

        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);
        CREATE INDEX IF NOT EXISTS idx_subs_user ON user_subscriptions(user_id);
        CREATE INDEX IF NOT EXISTS idx_subs_type ON user_subscriptions(sub_type);
        CREATE INDEX IF NOT EXISTS idx_delivery_user ON delivery_history(user_id);
        CREATE INDEX IF NOT EXISTS idx_delivery_paper ON delivery_history(paper_id);
    """)
    conn.commit()


def _ensure_migration_table() -> None:
    """Ensure the schema_migrations table exists."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            description TEXT NOT NULL,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()


def get_current_version() -> int:
    """Get the current schema version from the database."""
    _ensure_migration_table()
    conn = get_connection()
    cursor = conn.execute("SELECT MAX(version) FROM schema_migrations")
    result = cursor.fetchone()[0]
    return result if result is not None else 0


def run_migrations(target_version: int | None = None) -> int:
    """Run all pending migrations up to the target version.

    Args:
        target_version: The version to migrate to. If None, runs all migrations.

    Returns:
        The number of migrations applied.
    """
    _ensure_migration_table()
    current = get_current_version()

    if target_version is None:
        target_version = max(v for v, _, _ in MIGRATIONS) if MIGRATIONS else 0

    applied = 0
    for version, description, migration_func in sorted(MIGRATIONS):
        if version > current and version <= target_version:
            logger.info("Applying migration %d: %s", version, description)
            migration_func()

            conn = get_connection()
            conn.execute(
                "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                (version, description)
            )
            conn.commit()
            applied += 1
            logger.info("Migration %d applied successfully", version)

    if applied == 0:
        logger.info("Database schema is up to date (version %d)", current)
    else:
        logger.info("Applied %d migration(s), now at version %d", applied, get_current_version())

    return applied
