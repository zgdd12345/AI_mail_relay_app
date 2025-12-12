"""Embedding generation and caching for analysis workflows."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import httpx
import numpy as np

from ..arxiv_parser import ArxivPaper
from ..config import AnalysisConfig
from ..repositories import EmbeddingRecord, EmbeddingRepository

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Protocol for embedding providers."""

    def embed_texts(self, texts: Sequence[str], model: str, dimension: int) -> List[np.ndarray]:
        raise NotImplementedError


class LocalEmbeddingClient(EmbeddingClient):
    """Deterministic local embedding generator (development fallback)."""

    def embed_texts(self, texts: Sequence[str], model: str, dimension: int) -> List[np.ndarray]:
        vectors: List[np.ndarray] = []
        for text in texts:
            seed_bytes = hashlib.sha256(text.encode("utf-8")).digest()[:8]
            seed = int.from_bytes(seed_bytes, byteorder="big", signed=False)
            rng = np.random.default_rng(seed)
            vector = rng.standard_normal(dimension, dtype=np.float32)
            norm = np.linalg.norm(vector)
            if norm > 0:
                vector = vector / norm
            vectors.append(vector.astype(np.float32))
        return vectors


class QwenEmbeddingClient(EmbeddingClient):
    """Embedding client for DashScope/Qwen."""

    def __init__(
        self,
        api_key: str,
        endpoint: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._endpoint = endpoint or (
            "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
        )
        self._timeout = timeout

    def embed_texts(self, texts: Sequence[str], model: str, dimension: int) -> List[np.ndarray]:
        if not texts:
            return []

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "input": {"texts": list(texts)},
            "parameters": {"dimension": dimension, "text_type": "document"},
        }

        try:
            resp = httpx.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network errors are runtime concerns
            raise RuntimeError(f"Failed to call Qwen embedding API: {exc}") from exc

        body = resp.json()
        embeddings = body.get("output", {}).get("embeddings", [])
        if not isinstance(embeddings, list) or len(embeddings) != len(texts):
            raise RuntimeError("Unexpected embedding response format from Qwen API.")

        vectors: List[np.ndarray] = []
        for item in embeddings:
            values = item.get("embedding")
            if not isinstance(values, list):
                raise RuntimeError("Missing embedding values in Qwen response.")
            vectors.append(np.asarray(values, dtype=np.float32))
        return vectors


def _chunk(items: Sequence[ArxivPaper], size: int) -> Iterable[List[ArxivPaper]]:
    for idx in range(0, len(items), size):
        yield list(items[idx : idx + size])


@dataclass
class EmbeddingResult:
    paper_id: int
    vector: np.ndarray
    model_name: str
    embedding_dim: int


class EmbeddingGenerator:
    """Generate embeddings for stored papers with caching."""

    def __init__(
        self,
        config: AnalysisConfig,
        embedding_repo: EmbeddingRepository,
        client: EmbeddingClient | None = None,
    ) -> None:
        self._config = config
        self._repo = embedding_repo
        self._client = client or self._build_client(config)

    def _build_client(self, config: AnalysisConfig) -> EmbeddingClient:
        provider = config.embedding_provider.lower()
        api_key = os.getenv("QWEN_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        if provider == "qwen" and api_key:
            return QwenEmbeddingClient(api_key=api_key)
        logger.warning(
            "Using LocalEmbeddingClient fallback. Set QWEN_API_KEY to enable real embeddings."
        )
        return LocalEmbeddingClient()

    def generate_for_papers(
        self,
        papers: Sequence[ArxivPaper],
        force: bool = False,
    ) -> List[EmbeddingRecord]:
        """Generate embeddings for provided papers and persist them."""
        valid_papers = [paper for paper in papers if paper.db_id is not None]
        if not valid_papers:
            logger.info("No papers with database IDs available for embedding generation.")
            return []

        paper_ids = [paper.db_id for paper in valid_papers if paper.db_id is not None]
        existing_ids = set() if force else self._repo.get_existing_ids(paper_ids)
        pending = [paper for paper in valid_papers if force or paper.db_id not in existing_ids]

        if not pending:
            logger.info("All %d paper embeddings already cached.", len(valid_papers))
            return []

        logger.info(
            "Generating embeddings for %d paper(s) using provider=%s model=%s",
            len(pending),
            self._config.embedding_provider,
            self._config.embedding_model,
        )

        saved: List[EmbeddingRecord] = []
        for batch in _chunk(pending, self._config.embedding_batch_size):
            texts = [self._compose_text(paper) for paper in batch]
            try:
                vectors = self._client.embed_texts(
                    texts,
                    self._config.embedding_model,
                    self._config.embedding_dim,
                )
            except RuntimeError as exc:
                if (
                    self._config.embedding_provider.lower() != "local"
                    and self._config.embedding_fallback_local
                ):
                    logger.warning(
                        "Embedding provider failed (%s); falling back to local deterministic embeddings.",
                        exc,
                    )
                    self._client = LocalEmbeddingClient()
                    vectors = self._client.embed_texts(
                        texts,
                        self._config.embedding_model,
                        self._config.embedding_dim,
                    )
                else:
                    raise
            if len(vectors) != len(batch):
                raise RuntimeError("Embedding client returned unexpected number of vectors.")

            records = [
                EmbeddingRecord(
                    paper_id=paper.db_id or -1,
                    embedding=vectors[idx],
                    model_name=self._config.embedding_model,
                    embedding_dim=self._config.embedding_dim,
                )
                for idx, paper in enumerate(batch)
            ]
            self._repo.upsert_embeddings(records)
            saved.extend(records)

        logger.info("Embedded and cached %d paper(s).", len(saved))
        return saved

    def load_embeddings_map(self, papers: Sequence[ArxivPaper]) -> dict[int, EmbeddingRecord]:
        """Return a mapping of paper_id -> embedding record for the provided papers."""
        paper_ids = [paper.db_id for paper in papers if paper.db_id is not None]
        if not paper_ids:
            return {}
        return self._repo.get_by_paper_ids(paper_ids)

    @staticmethod
    def _compose_text(paper: ArxivPaper) -> str:
        """Combine key fields into a single embedding input string."""
        parts = [
            paper.title.strip(),
            paper.research_field.strip(),
            paper.summary.strip(),
            paper.abstract.strip(),
        ]
        return "\n".join([part for part in parts if part])


__all__ = [
    "EmbeddingGenerator",
    "EmbeddingClient",
    "LocalEmbeddingClient",
    "QwenEmbeddingClient",
    "EmbeddingResult",
]
