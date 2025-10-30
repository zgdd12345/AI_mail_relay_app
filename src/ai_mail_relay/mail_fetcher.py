"""IMAP helper utilities for fetching arXiv subscription emails."""

from __future__ import annotations

import imaplib
import logging
from datetime import date
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import Iterable, List

from .config import MailboxConfig


LOGGER = logging.getLogger(__name__)


class MailFetcher:
    """Fetch unread emails from an IMAP inbox."""

    def __init__(self, config: MailboxConfig) -> None:
        self._config = config

    def _connect(self) -> imaplib.IMAP4_SSL:
        LOGGER.debug(
            "Connecting to IMAP server %s:%s", self._config.imap_host, self._config.imap_port
        )
        client = imaplib.IMAP4_SSL(self._config.imap_host, self._config.imap_port)
        client.login(self._config.imap_user, self._config.imap_password)
        client.select(self._config.imap_folder)
        return client

    def fetch_unread_messages(self, since: date) -> List[EmailMessage]:
        """Return unseen messages received on or after the given date."""
        date_str = since.strftime("%d-%b-%Y")
        search_terms = ["UNSEEN", f"SINCE {date_str}"]
        if self._config.sender_filter:
            search_terms.append(f'FROM "{self._config.sender_filter}"')

        criteria = "(" + " ".join(search_terms) + ")"

        LOGGER.info("Searching IMAP folder=%s with criteria=%s", self._config.imap_folder, criteria)

        with self._connect() as client:
            status, response = client.search(None, criteria)
            if status != "OK":
                LOGGER.warning("IMAP search failed with status %s: %s", status, response)
                return []

            message_ids: Iterable[str] = response[0].decode().split()
            messages: List[EmailMessage] = []

            for msg_id in message_ids:
                status, data = client.fetch(msg_id, "(RFC822)")
                if status != "OK" or not data or data[0] is None:
                    LOGGER.warning("Failed to fetch message id=%s", msg_id)
                    continue

                _, raw_message = data[0]
                email_message = message_from_bytes(raw_message, policy=policy.default)
                if isinstance(email_message, EmailMessage):
                    messages.append(email_message)
                else:
                    LOGGER.warning("Skipping non-EmailMessage payload for id=%s", msg_id)

            LOGGER.info("Fetched %d unread messages", len(messages))
            return messages


def message_is_relevant(message: EmailMessage, subject_keywords: Iterable[str]) -> bool:
    """Return True when the subject contains any of the subject keywords."""
    subject = message.get("Subject", "").lower()
    return any(keyword.lower() in subject for keyword in subject_keywords)


__all__ = ["MailFetcher", "message_is_relevant"]
