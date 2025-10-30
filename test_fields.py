#!/usr/bin/env python3
"""Test to verify research_field and summary are extracted correctly."""

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

print(f"Found {len(relevant_messages)} relevant messages")

# Parse papers
papers = []
for message in relevant_messages:
    payload = get_plain_text_body(message)
    if payload:
        parsed = parse_arxiv_email(payload)
        papers.extend(parsed)

# Filter papers
filtered_papers = filter_papers(
    papers, settings.filtering.allowed_categories, settings.filtering.keyword_filters
)

# LIMIT TO 3 PAPERS FOR TESTING
test_papers = filtered_papers[:3]

print(f"\n{'='*80}")
print(f"Processing {len(test_papers)} papers individually...")
print(f"{'='*80}\n")

# Generate summary with LLM
llm_client = LLMClient(settings.llm)
summary = llm_client.summarize_papers(test_papers)

print(f"\n{'='*80}")
print("Verifying Extracted Fields:")
print(f"{'='*80}\n")

for idx, paper in enumerate(test_papers, 1):
    print(f"Paper {idx}: {paper.title[:60]}...")
    print(f"  arXiv ID: {paper.arxiv_id}")
    print(f"  ✓ Research Field: {paper.research_field or '(NOT EXTRACTED)'}")
    print(f"  ✓ Work Summary: {paper.summary[:100] if paper.summary else '(NOT EXTRACTED)'}...")
    print()

# Check if all fields are populated
missing_fields = []
for idx, paper in enumerate(test_papers, 1):
    if not paper.research_field:
        missing_fields.append(f"Paper {idx} missing research_field")
    if not paper.summary:
        missing_fields.append(f"Paper {idx} missing summary")

if missing_fields:
    print("❌ FAILED - Missing fields:")
    for msg in missing_fields:
        print(f"  - {msg}")
else:
    print("✅ SUCCESS - All papers have both research_field and summary!")
