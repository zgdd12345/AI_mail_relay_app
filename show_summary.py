#!/usr/bin/env python3
"""Show the full AI summary generated for the test papers."""

from datetime import datetime, UTC, timedelta
from dotenv import load_dotenv
from ai_mail_relay.config import Settings
from ai_mail_relay.mail_fetcher import MailFetcher, message_is_relevant
from ai_mail_relay.pipeline import get_plain_text_body, message_is_from_today
from ai_mail_relay.arxiv_parser import parse_arxiv_email, filter_papers
from ai_mail_relay.llm_client import LLMClient

load_dotenv()

settings = Settings()
settings.validate()

# Fetch emails
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

# Parse and filter papers
papers = []
for message in relevant_messages:
    payload = get_plain_text_body(message)
    if payload:
        parsed = parse_arxiv_email(payload)
        papers.extend(parsed)

filtered_papers = filter_papers(
    papers, settings.filtering.allowed_categories, settings.filtering.keyword_filters
)

# Use only first 3 for testing
test_papers = filtered_papers[:3]

# Generate summary
llm_client = LLMClient(settings.llm)
summary = llm_client.summarize_papers(test_papers)

print(f"\n{'='*80}")
print("完整的 AI 摘要:")
print(f"{'='*80}\n")
print(summary)
print(f"\n{'='*80}")
