"""Data access repositories for AI Mail Relay."""

from .cluster_repository import (
    ClusterPaperLink,
    ClusterRecord,
    ClusterRepository,
    ClusterRun,
    TrendSnapshot,
)
from .embedding_repository import EmbeddingRecord, EmbeddingRepository
from .paper_repository import PaperRepository
from .subscription_repository import SubscriptionRepository
from .user_repository import User, UserRepository

__all__ = [
    "PaperRepository",
    "SubscriptionRepository",
    "User",
    "UserRepository",
    "EmbeddingRepository",
    "EmbeddingRecord",
    "ClusterRepository",
    "ClusterRun",
    "ClusterRecord",
    "ClusterPaperLink",
    "TrendSnapshot",
]
