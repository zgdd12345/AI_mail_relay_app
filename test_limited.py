#!/usr/bin/env python3
"""Test script with limited papers for faster testing."""

from datetime import datetime, UTC, timedelta
from dotenv import load_dotenv
from ai_mail_relay.config import Settings
from ai_mail_relay.mail_fetcher import MailFetcher, message_is_relevant
from ai_mail_relay.pipeline import get_plain_text_body, message_is_from_today
from ai_mail_relay.arxiv_parser import parse_arxiv_email, filter_papers
from ai_mail_relay.llm_client import LLMClient
from ai_mail_relay.mail_sender import MailSender

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

print(f"Found {len(relevant_messages)} relevant messages")

# Parse papers
papers = []
for message in relevant_messages:
    payload = get_plain_text_body(message)
    if payload:
        parsed = parse_arxiv_email(payload)
        papers.extend(parsed)

print(f"Parsed {len(papers)} total papers")

# Filter papers
filtered_papers = filter_papers(
    papers, settings.filtering.allowed_categories, settings.filtering.keyword_filters
)

print(f"Filtered to {len(filtered_papers)} AI papers")

# LIMIT TO 3 PAPERS FOR TESTING
test_papers = filtered_papers[:3]
print(f"\n{'='*60}")
print(f"Testing with {len(test_papers)} papers:")
print(f"{'='*60}\n")

for idx, paper in enumerate(test_papers, 1):
    print(f"{idx}. {paper.title}")
    print(f"   arXiv ID: {paper.arxiv_id}")
    print(f"   Categories: {', '.join(paper.categories)}")
    print(f"   Authors: {paper.authors[:100]}...")
    if paper.affiliations:
        print(f"   Affiliations: {paper.affiliations[:100]}...")
    print()

# Generate summary with LLM
print("Generating AI summaries...")
llm_client = LLMClient(settings.llm)
summary = llm_client.summarize_papers(test_papers)

print(f"\n{'='*60}")
print("AI Summary Generated:")
print(f"{'='*60}")
print(summary[:500])
print("...\n")

# Send email
print("Sending email...")
sender = MailSender(settings.outbox)
sender.send_digest(summary, test_papers)

print("\n✓ Email sent successfully!")
print("Please check your inbox.")
