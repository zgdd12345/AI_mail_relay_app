"""Repository for user CRUD operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

from ..database.connection import get_connection

logger = logging.getLogger(__name__)


@dataclass
class User:
    """Domain model for an application user."""

    id: int
    email: str
    name: str | None
    is_active: bool
    created_at: str | None = None
    updated_at: str | None = None


class UserRepository:
    """Data access layer for users."""

    def create(self, email: str, name: str | None = None) -> int:
        """Create a new user."""
        conn = get_connection()
        cursor = conn.execute(
            """
            INSERT INTO users (email, name, is_active)
            VALUES (?, ?, 1)
            """,
            (email, name or None),
        )
        conn.commit()
        user_id = cursor.lastrowid
        logger.debug("Created user %s with id %d", email, user_id)
        return user_id

    def find_by_email(self, email: str) -> User | None:
        """Fetch a user by email."""
        conn = get_connection()
        cursor = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        )
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def find_active(self) -> List[User]:
        """Return all active users."""
        conn = get_connection()
        cursor = conn.execute(
            "SELECT * FROM users WHERE is_active = 1 ORDER BY created_at ASC"
        )
        return [self._row_to_user(row) for row in cursor.fetchall()]

    def find_all(self) -> List[User]:
        """Return all users (active and inactive)."""
        conn = get_connection()
        cursor = conn.execute(
            "SELECT * FROM users ORDER BY created_at ASC"
        )
        return [self._row_to_user(row) for row in cursor.fetchall()]

    def set_active(self, email: str, is_active: bool) -> int:
        """Activate or deactivate a user by email."""
        conn = get_connection()
        cursor = conn.execute(
            """
            UPDATE users
            SET is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE email = ?
            """,
            (1 if is_active else 0, email),
        )
        conn.commit()
        return cursor.rowcount

    def exists(self, email: str) -> bool:
        """Check if a user already exists."""
        conn = get_connection()
        cursor = conn.execute(
            "SELECT 1 FROM users WHERE email = ?",
            (email,),
        )
        return cursor.fetchone() is not None

    @staticmethod
    def _row_to_user(row) -> User:
        """Convert a database row to a User."""
        return User(
            id=row["id"],
            email=row["email"],
            name=row["name"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


__all__ = ["User", "UserRepository"]
