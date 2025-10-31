# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Mail Relay is a Python application that fetches arXiv subscription emails from an IMAP mailbox, filters AI-related papers by category/keywords, generates summaries using various LLM providers (OpenAI, DeepSeek, Claude, Qwen, ByteDance), and forwards digest emails via SMTP.

The application is designed for daily automated execution (e.g., via cron) to process arXiv daily digests.

## Installation & Setup

```bash
# Install in editable mode
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"
```

## Running the Application

```bash
# Standard execution
ai-mail-relay

# With debug logging
ai-mail-relay --log-level DEBUG

# Run as module (useful for development)
python -m ai_mail_relay.main --log-level DEBUG
```

## Configuration

All configuration is via environment variables or a `.env` file in the project root. See [config.py](src/ai_mail_relay/config.py) for all available settings and their defaults.

Required environment variables:
- `ARXIV_FETCH_MODE`: "api" (default, recommended) or "email"
- API mode: No IMAP credentials required
- Email mode: `IMAP_HOST`, `IMAP_USER`, `IMAP_PASSWORD`
- Both modes: `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM_ADDRESS`, `MAIL_TO_ADDRESS` (email sending)
- `LLM_API_KEY` (or `OPENAI_API_KEY` for backward compatibility)

## Architecture

The application follows a linear pipeline architecture orchestrated by [pipeline.py](src/ai_mail_relay/pipeline.py):

1. **Paper Fetching** (dual-mode support)
   - **API Mode** ([arxiv_fetcher.py](src/ai_mail_relay/arxiv_fetcher.py)) - Default, recommended
     - Fetches papers directly from arXiv API (`https://export.arxiv.org/api/query`)
     - **Default behavior: fetches yesterday's papers** (matches arXiv announcement schedule)
     - Queries by category with configurable max results (`ARXIV_API_MAX_RESULTS`)
     - Parses XML response using `xml.etree.ElementTree`
     - Respects arXiv rate limit (3-second delay between requests)
     - Filters papers by publication date locally
     - Returns `List[ArxivPaper]` directly
   - **Email Mode** ([mail_fetcher.py](src/ai_mail_relay/mail_fetcher.py)) - Legacy
     - Connects to IMAP server and fetches unread messages within date range
     - Filters by sender (`MAIL_SENDER_FILTER`) and subject keywords (`MAIL_SUBJECT_KEYWORDS`)
     - Parses email body text using regex patterns

2. **Paper Parsing** ([arxiv_parser.py](src/ai_mail_relay/arxiv_parser.py))
   - Defines `ArxivPaper` dataclass representing each paper
   - Email mode: Extracts paper metadata from email body using regex
   - API mode: Directly populates `ArxivPaper` from XML data
   - Uses regex to split entries by "Title:" markers and parse structured fields (email mode only)

3. **Filtering**
   - Papers are filtered by category whitelist (`ARXIV_ALLOWED_CATEGORIES`) or keyword matching (`ARXIV_KEYWORDS`)
   - Categories use arXiv taxonomy (e.g., cs.AI, cs.LG, cs.CV)
   - Papers are deduplicated by normalized title

4. **LLM Summarization** ([llm_client.py](src/ai_mail_relay/llm_client.py), [llm_providers.py](src/ai_mail_relay/llm_providers.py))
   - Provider abstraction via `BaseLLMProvider` with concrete implementations per LLM service
   - OpenAI-compatible providers (OpenAI, DeepSeek, Qwen, ByteDance) share `OpenAICompatibleProvider` base
   - Anthropic/Claude uses its own Messages API adapter
   - Each provider auto-adjusts endpoint URLs when default OpenAI endpoint is detected
   - All providers use `httpx` for HTTP requests with configurable timeouts

5. **Mail Sending** ([mail_sender.py](src/ai_mail_relay/mail_sender.py))
   - Sends digest email with summary in body and full paper details as Markdown attachment
   - Uses SMTP with optional STARTTLS or SMTP_SSL
   - Implements timeout handling and automatic retry with exponential backoff
   - Configurable via `SMTP_TIMEOUT`, `SMTP_RETRY_ATTEMPTS`, `SMTP_RETRY_BASE_DELAY`

### Configuration System

[config.py](src/ai_mail_relay/config.py) uses frozen dataclasses for immutability:
- `ArxivConfig`: Fetching mode ("api" or "email") and API-specific settings (NEW)
- `MailboxConfig`: IMAP settings and email filtering rules (only validated in email mode)
- `OutboxConfig`: SMTP settings, recipient addresses, and connection parameters
  - `smtp_timeout`: Connection timeout in seconds (default: 30)
  - `smtp_retry_attempts`: Number of retry attempts on failure (default: 3)
  - `smtp_retry_base_delay`: Base delay in seconds for exponential backoff (default: 2.0)
- `FilteringConfig`: arXiv category/keyword filters and date range
- `LLMConfig`: LLM provider, model, API credentials, and request parameters
- `Settings`: Top-level container with `validate()` for required field checks

Environment variables are read via `os.getenv()` in field factories. Helper functions `_get_env_list()` and `_get_env_bool()` parse comma-separated lists and boolean values.

The `Settings.validate()` method conditionally validates IMAP credentials only when `ARXIV_FETCH_MODE=email`.

### LLM Provider System

The provider system uses a registry pattern in [llm_client.py](src/ai_mail_relay/llm_client.py:28-34):
- `LLMClient` selects the provider class based on `LLM_PROVIDER` config
- All providers implement `BaseLLMProvider.generate(prompt: str) -> str`
- Provider-specific endpoint construction happens in `__init__`
- Providers automatically swap default OpenAI endpoint to their own service URLs
- Error handling via `LLMProviderError` for HTTP failures

### Concurrency and Rate Limiting

[llm_client.py](src/ai_mail_relay/llm_client.py) implements multi-threaded concurrent LLM requests:
- `ThreadPoolExecutor` with configurable worker count (`LLM_MAX_CONCURRENT`, default 4)
- `RateLimiter` class enforces requests-per-minute limits using a fixed-window algorithm
- `summarize_papers()` uses `asyncio.gather()` with `loop.run_in_executor()` to parallelize API calls
- Automatic retry with exponential backoff on 429 rate limit errors (configurable via `LLM_RETRY_ON_RATE_LIMIT`)
- Configuration via environment variables:
  - `LLM_MAX_CONCURRENT`: Maximum concurrent threads (default: 4)
  - `LLM_RATE_LIMIT_RPM`: Maximum requests per minute (0 = unlimited, default: 20)
  - `LLM_RETRY_ON_RATE_LIMIT`: Enable retry on 429 errors (default: true)
  - `LLM_RETRY_ATTEMPTS`: Number of retry attempts (default: 3)
  - `LLM_RETRY_BASE_DELAY`: Base delay in seconds for exponential backoff (default: 1.0)

### Email Parsing Logic

[arxiv_parser.py](src/ai_mail_relay/arxiv_parser.py) parsing strategy:
- Split email body by regex `/^Title:\s/i` to isolate paper entries
- For each entry, scan lines for field markers (Title:, Authors:, Categories:, Abstract:)
- Abstract collection continues until blank line encountered
- Category extraction via regex `/([a-z\-]+\.[A-Z0-9\-]+)/` for arXiv taxonomy format
- Link extraction via generic URL regex

## Development Notes

- The codebase uses Python 3.10+ type hints extensively (PEP 604 union syntax `X | Y`)
- All modules have `__all__` exports for clean public APIs
- Logging is done via standard library `logging` with module-level loggers
- No test suite currently exists (no `test_*.py` files found)
- Entry point is registered in [pyproject.toml](pyproject.toml:16) as `ai-mail-relay`
- Primary dependency is `httpx` for async-capable HTTP; no dependency on official OpenAI/Anthropic SDKs
- The application is stateless: each run is independent, no database or persistent state

## Common Pitfalls

- **Provider endpoint configuration**: When adding support for a new provider or debugging API calls, note that providers auto-replace the OpenAI default endpoint. Check [llm_providers.py](src/ai_mail_relay/llm_providers.py) for endpoint construction logic.
- **Email parsing fragility**: The arxiv parser expects specific "Title:", "Authors:", "Categories:", "Abstract:" markers in plain-text email body. HTML emails or format changes will break parsing.
- **Configuration validation**: Settings validation only happens in [main.py](src/ai_mail_relay/main.py:36) after `Settings()` construction. Missing required env vars will cause `ValueError` at startup.
- **Timezone handling**: Date filtering in [pipeline.py](src/ai_mail_relay/pipeline.py:102-118) uses UTC consistently. Email Date headers are converted to UTC for comparison.
- **SMTP connection issues**: Network connectivity problems (firewalls, blocked ports) are common on cloud servers. See troubleshooting section below.

## Troubleshooting

For comprehensive troubleshooting guidance, see the **[Troubleshooting Guide](docs/troubleshooting.md)**.

### Quick Reference

**SMTP Connection Issues:**
- Run diagnostic: `./deploy/diagnose.sh`
- Check security groups for outbound port 587/465
- Try alternative port 465: `SMTP_PORT=465`, `SMTP_USE_TLS=false`
- Use app-specific password for Gmail: https://myaccount.google.com/apppasswords

**Timeout and Retry Configuration:**
```bash
SMTP_TIMEOUT=30              # Connection timeout (seconds)
SMTP_RETRY_ATTEMPTS=3        # Number of retries
SMTP_RETRY_BASE_DELAY=2.0    # Base delay for exponential backoff
```

**Debug Logging:**
```bash
ai-mail-relay --log-level DEBUG
```

See [docs/troubleshooting.md](docs/troubleshooting.md) for detailed diagnostic procedures and solutions.
