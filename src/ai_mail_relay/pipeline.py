"""Core orchestration logic for the AI mail relay."""

from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage
from email.utils import parsedate_to_datetime
from typing import Iterable, List

from .arxiv_parser import ArxivPaper, filter_papers, parse_arxiv_email
from .config import Settings
from .llm_client import LLMClient
from .mail_fetcher import MailFetcher, message_is_relevant
from .mail_sender import MailSender


LOGGER = logging.getLogger(__name__)


def run_pipeline(settings: Settings) -> None:
    """Fetch unread arXiv emails, summarize, and forward the digest."""
    target_date = datetime.now(UTC).date()
    oldest_date = target_date - timedelta(days=settings.filtering.max_days_back - 1)

    fetcher = MailFetcher(settings.mailbox)
    messages = fetcher.fetch_unread_messages(since=oldest_date)

    relevant_messages = [
        message
        for message in messages
        if message_is_relevant(message, settings.mailbox.subject_keywords)
        and message_is_from_today(message, target_date, settings.filtering.max_days_back)
    ]

    LOGGER.info(
        "Identified %d relevant arXiv emails (out of %d fetched)",
        len(relevant_messages),
        len(messages),
    )

    # 如果没有找到相关邮件，直接返回不发送邮件
    if not relevant_messages:
        LOGGER.info("No relevant arXiv emails found, skipping email sending")
        return

    papers = extract_papers(relevant_messages)
    LOGGER.info("Parsed %d total papers before filtering", len(papers))

    # 如果没有解析出任何论文，直接返回不发送邮件
    if not papers:
        LOGGER.info("No papers parsed from emails, skipping email sending")
        return

    filtered_papers = filter_papers(
        papers, settings.filtering.allowed_categories, settings.filtering.keyword_filters
    )

    LOGGER.info("Retained %d AI-related papers after filtering", len(filtered_papers))

    # 如果过滤后没有论文，直接返回不发送邮件
    if not filtered_papers:
        LOGGER.info("No AI-related papers after filtering, skipping email sending")
        return

    unique_papers = deduplicate_papers(filtered_papers)
    LOGGER.info("Deduplicated papers down to %d unique entries", len(unique_papers))

    # 如果去重后没有论文，直接返回不发送邮件
    if not unique_papers:
        LOGGER.info("No unique papers after deduplication, skipping email sending")
        return

    # 只有在有论文的情况下才生成摘要和发送邮件
    llm_client = LLMClient(settings.llm)
    summary = llm_client.summarize_papers(unique_papers)

    sender = MailSender(settings.outbox)
    sender.send_digest(summary, unique_papers)

    LOGGER.info("Successfully sent digest email with %d papers", len(unique_papers))


def extract_papers(messages: Iterable[EmailMessage]) -> List[ArxivPaper]:
    """Extract ArxivPaper objects from the supplied email messages."""
    papers: List[ArxivPaper] = []
    for message in messages:
        payload = get_plain_text_body(message)
        if not payload:
            continue
        parsed = parse_arxiv_email(payload)
        papers.extend(parsed)
    return papers


def get_plain_text_body(message: EmailMessage) -> str:
    """Return the first text/plain payload from the email."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                charset = part.get_content_charset("utf-8")
                try:
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:  # pragma: no cover - defensive fallback
                    continue
    else:
        charset = message.get_content_charset("utf-8")
        payload = message.get_payload(decode=True)
        if payload:
            return payload.decode(charset, errors="replace")
    return ""


def deduplicate_papers(papers: Iterable[ArxivPaper]) -> List[ArxivPaper]:
    """Deduplicate papers by title while preserving order."""
    unique: "OrderedDict[str, ArxivPaper]" = OrderedDict()
    for paper in papers:
        normalized_title = paper.title.strip().lower()
        if normalized_title not in unique:
            unique[normalized_title] = paper
    return list(unique.values())


def message_is_from_today(
    message: EmailMessage, today: date, max_days_back: int
)  -> bool:
    """Return True if the email was sent within the configured window."""
    header = message.get("Date")
    if not header:
        return True
    try:
        sent_at = parsedate_to_datetime(header)
    except (TypeError, ValueError):
        return True

    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=UTC)
    sent_date = sent_at.astimezone(UTC).date()

    return today - timedelta(days=max_days_back - 1) <= sent_date <= today


__all__ = ["run_pipeline"]

