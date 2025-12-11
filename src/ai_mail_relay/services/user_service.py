"""User and subscription business logic."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, List

from ..arxiv_parser import ArxivPaper
from ..repositories.subscription_repository import SubscriptionRepository
from ..repositories.user_repository import User, UserRepository

logger = logging.getLogger(__name__)


@dataclass
class UserSubscriptions:
    """Aggregated subscriptions for a user."""

    categories: list[str]
    keywords: list[str]


class UserService:
    """Service for managing users and their subscriptions."""

    def __init__(self) -> None:
        self._users = UserRepository()
        self._subscriptions = SubscriptionRepository()

    # User management -------------------------------------------------
    def create_user(self, email: str, name: str | None = None) -> User:
        """Create a user if not exists and return it."""
        if self._users.exists(email):
            user = self._users.find_by_email(email)
            assert user is not None  # for type checker
            return user

        user_id = self._users.create(email=email, name=name)
        user = self._users.find_by_email(email)
        if user is None:
            raise RuntimeError("User creation failed unexpectedly")
        logger.info("User created: %s (id=%d)", email, user_id)
        return user

    def get_active_users(self) -> List[User]:
        """Return active users."""
        return self._users.find_active()

    def get_user(self, email: str) -> User | None:
        """Fetch a user by email."""
        return self._users.find_by_email(email)

    def list_users(self) -> List[User]:
        """Return all users."""
        return self._users.find_all()

    def set_active(self, email: str, is_active: bool) -> bool:
        """Activate or deactivate a user."""
        updated = self._users.set_active(email, is_active)
        return updated > 0

    # Subscription management ----------------------------------------
    def subscribe(
        self,
        user: User,
        categories: Iterable[str] | None = None,
        keywords: Iterable[str] | None = None,
    ) -> int:
        """Subscribe a user to categories and/or keywords."""
        added = 0
        for category in categories or []:
            if category:
                added += int(self._subscriptions.add_subscription(user.id, "category", category))
        for keyword in keywords or []:
            if keyword:
                added += int(self._subscriptions.add_subscription(user.id, "keyword", keyword))
        return added

    def unsubscribe(
        self,
        user: User,
        categories: Iterable[str] | None = None,
        keywords: Iterable[str] | None = None,
    ) -> int:
        """Remove subscriptions for the user."""
        removed = 0
        for category in categories or []:
            removed += self._subscriptions.remove(user.id, "category", category)
        for keyword in keywords or []:
            removed += self._subscriptions.remove(user.id, "keyword", keyword)
        return removed

    def get_subscriptions(self, user: User) -> UserSubscriptions:
        """Return user's subscriptions."""
        subs = self._subscriptions.get_user_subscriptions(user.id)
        return UserSubscriptions(categories=subs["categories"], keywords=subs["keywords"])

    # Paper routing ---------------------------------------------------
    def get_papers_for_user(self, user: User, papers: List[ArxivPaper]) -> List[ArxivPaper]:
        """Filter papers based on a user's subscriptions.

        If no subscriptions are configured, all papers are returned.
        """
        subs = self.get_subscriptions(user)
        if not subs.categories and not subs.keywords:
            return papers

        filtered: list[ArxivPaper] = []
        for paper in papers:
            if subs.categories and paper.matches_category(subs.categories):
                filtered.append(paper)
                continue
            if subs.keywords and paper.matches_keyword(subs.keywords):
                filtered.append(paper)

        return filtered


__all__ = ["UserService", "UserSubscriptions"]
