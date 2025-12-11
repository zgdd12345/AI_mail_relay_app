"""Repository for user subscription management."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

from ..database.connection import get_connection

logger = logging.getLogger(__name__)

VALID_TYPES = {"category", "keyword"}


@dataclass
class Subscription:
    """Domain model for a subscription record."""

    id: int
    user_id: int
    sub_type: str
    value: str


class SubscriptionRepository:
    """Data access layer for subscriptions."""

    def add_subscription(self, user_id: int, sub_type: str, value: str) -> bool:
        """Add a subscription entry."""
        sub_type = sub_type.lower()
        if sub_type not in VALID_TYPES:
            raise ValueError(f"Invalid subscription type: {sub_type}")

        normalized = self._normalize(value)
        conn = get_connection()
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO user_subscriptions (user_id, sub_type, value)
            VALUES (?, ?, ?)
            """,
            (user_id, sub_type, normalized),
        )
        conn.commit()
        inserted = cursor.rowcount > 0
        if inserted:
            logger.debug("Added %s subscription '%s' for user %d", sub_type, normalized, user_id)
        return inserted

    def remove(self, user_id: int, sub_type: str, value: str) -> int:
        """Remove a subscription entry."""
        sub_type = sub_type.lower()
        normalized = self._normalize(value)
        conn = get_connection()
        cursor = conn.execute(
            """
            DELETE FROM user_subscriptions
            WHERE user_id = ? AND sub_type = ? AND value = ?
            """,
            (user_id, sub_type, normalized),
        )
        conn.commit()
        return cursor.rowcount

    def get_user_subscriptions(self, user_id: int) -> Dict[str, List[str]]:
        """Return a mapping of subscription types to values."""
        conn = get_connection()
        cursor = conn.execute(
            """
            SELECT sub_type, value
            FROM user_subscriptions
            WHERE user_id = ?
            ORDER BY id ASC
            """,
            (user_id,),
        )

        categories: list[str] = []
        keywords: list[str] = []
        for row in cursor.fetchall():
            if row["sub_type"] == "category":
                categories.append(row["value"])
            elif row["sub_type"] == "keyword":
                keywords.append(row["value"])

        return {"categories": categories, "keywords": keywords}

    @staticmethod
    def _normalize(value: str) -> str:
        """Normalize user-provided values for consistent matching."""
        return value.strip().lower()


__all__ = ["Subscription", "SubscriptionRepository"]
