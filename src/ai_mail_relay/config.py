"""Configuration management for the AI mail relay application."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


def _get_env_list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class MailboxConfig:
    imap_host: str = field(default_factory=lambda: os.getenv("IMAP_HOST", ""))
    imap_port: int = field(
        default_factory=lambda: int(os.getenv("IMAP_PORT", "993"))
    )
    imap_user: str = field(default_factory=lambda: os.getenv("IMAP_USER", ""))
    imap_password: str = field(
        default_factory=lambda: os.getenv("IMAP_PASSWORD", "")
    )
    imap_folder: str = field(default_factory=lambda: os.getenv("IMAP_FOLDER", "INBOX"))
    sender_filter: str = field(
        default_factory=lambda: os.getenv("MAIL_SENDER_FILTER", "no-reply@arxiv.org")
    )
    subject_keywords: List[str] = field(
        default_factory=lambda: _get_env_list(
            "MAIL_SUBJECT_KEYWORDS", ["arXiv", "Daily", "digest"]
        )
    )

    def validate(self) -> None:
        required = {
            "IMAP_HOST": self.imap_host,
            "IMAP_USER": self.imap_user,
            "IMAP_PASSWORD": self.imap_password,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Missing required IMAP configuration: {', '.join(sorted(missing))}"
            )


@dataclass(frozen=True)
class OutboxConfig:
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = field(
        default_factory=lambda: int(os.getenv("SMTP_PORT", "587"))
    )
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(
        default_factory=lambda: os.getenv("SMTP_PASSWORD", "")
    )
    use_tls: bool = field(
        default_factory=lambda: _get_env_bool("SMTP_USE_TLS", True)
    )
    from_address: str = field(
        default_factory=lambda: os.getenv("MAIL_FROM_ADDRESS", "")
    )
    to_address: str = field(default_factory=lambda: os.getenv("MAIL_TO_ADDRESS", ""))

    def validate(self) -> None:
        required = {
            "SMTP_HOST": self.smtp_host,
            "SMTP_USER": self.smtp_user,
            "SMTP_PASSWORD": self.smtp_password,
            "MAIL_FROM_ADDRESS": self.from_address,
            "MAIL_TO_ADDRESS": self.to_address,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Missing required SMTP configuration: {', '.join(sorted(missing))}"
            )


@dataclass(frozen=True)
class FilteringConfig:
    allowed_categories: List[str] = field(
        default_factory=lambda: _get_env_list(
            "ARXIV_ALLOWED_CATEGORIES",
            [
                "cs.AI",
                "cs.LG",
                "cs.CV",
                "cs.CL",
                "cs.RO",
                "cs.IR",
                "stat.ML",
                "eess.AS",
            ],
        )
    )
    keyword_filters: List[str] = field(
        default_factory=lambda: _get_env_list(
            "ARXIV_KEYWORDS",
            ["artificial intelligence", "machine learning", "deep learning"],
        )
    )
    max_days_back: int = field(
        default_factory=lambda: int(os.getenv("ARXIV_MAX_DAYS_BACK", "1"))
    )


@dataclass(frozen=True)
class LLMConfig:
    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    api_key: str = field(
        default_factory=lambda: os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    )
    model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    )
    endpoint: str = field(
        default_factory=lambda: os.getenv(
            "LLM_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
        )
    )
    response_format: str = field(
        default_factory=lambda: os.getenv("SUMMARY_FORMAT", "markdown")
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("SUMMARY_MAX_TOKENS", "1024"))
    )
    request_timeout: int = field(
        default_factory=lambda: int(os.getenv("LLM_REQUEST_TIMEOUT", "60"))
    )
    anthropic_version: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_VERSION", "2023-06-01")
    )

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY (or generic LLM API key) must be provided for summarization.")
        provider = self.provider.lower()
        if provider not in {"openai", "deepseek", "claude", "anthropic", "qwen", "bytedance"}:
            raise ValueError(
                f"Unsupported LLM provider '{self.provider}'. "
                "Valid options: openai, deepseek, claude, anthropic, qwen, bytedance."
            )


@dataclass(frozen=True)
class Settings:
    mailbox: MailboxConfig = field(default_factory=MailboxConfig)
    outbox: OutboxConfig = field(default_factory=OutboxConfig)
    filtering: FilteringConfig = field(default_factory=FilteringConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    def validate(self) -> None:
        self.mailbox.validate()
        self.outbox.validate()
        self.llm.validate()


def today_string() -> str:
    """Return today's date string formatted for logging and filenames."""
    return datetime.utcnow().strftime("%Y-%m-%d")


__all__ = [
    "MailboxConfig",
    "OutboxConfig",
    "FilteringConfig",
    "LLMConfig",
    "Settings",
    "today_string",
]
