# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Mail Relay is a Python application that fetches arXiv papers via the arXiv API, filters AI-related papers by category/keywords, generates summaries using various LLM providers (OpenAI, DeepSeek, Claude, Qwen, ByteDance), and forwards digest emails via SMTP.

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
- `ARXIV_FETCH_MODE`: must be `api` (email mode removed)
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM_ADDRESS`, `MAIL_TO_ADDRESS`
- `LLM_API_KEY` (or `OPENAI_API_KEY` for backward compatibility)

## Architecture

The application follows a linear pipeline architecture orchestrated by [pipeline.py](src/ai_mail_relay/pipeline.py):

1. **Paper Fetching** ([arxiv_fetcher.py](src/ai_mail_relay/arxiv_fetcher.py))
   - Fetches papers directly from arXiv API (`https://export.arxiv.org/api/query`)
   - **Default behavior: fetches yesterday's papers** (matches arXiv announcement schedule)
   - Queries by category with configurable max results (`ARXIV_API_MAX_RESULTS`)
   - Parses XML response using `xml.etree.ElementTree`
   - Respects arXiv rate limit (3-second delay between requests)
   - Filters papers by publication date locally
   - Returns `List[ArxivPaper]` directly

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

6. **Database Layer** (NEW - [database/](src/ai_mail_relay/database/))
   - SQLite-based persistent storage with WAL mode for better concurrency
   - [connection.py](src/ai_mail_relay/database/connection.py): Thread-local connection management
   - [migrations.py](src/ai_mail_relay/database/migrations.py): Schema versioning and migrations
   - [repositories/paper_repository.py](src/ai_mail_relay/repositories/paper_repository.py): Paper CRUD operations
   - [services/paper_service.py](src/ai_mail_relay/services/paper_service.py): Deduplication logic

### User Management System (NEW)

- Repositories: [user_repository.py](src/ai_mail_relay/repositories/user_repository.py) and [subscription_repository.py](src/ai_mail_relay/repositories/subscription_repository.py) manage users and subscriptions.
- Services: [user_service.py](src/ai_mail_relay/services/user_service.py) filters papers per user; [delivery_service.py](src/ai_mail_relay/services/delivery_service.py) tracks delivery history to skip already-sent papers (configurable via `SKIP_DELIVERED_PAPERS`).
- CLI: `ai-mail-relay user add/list/show/activate/deactivate/subscribe/unsubscribe/subscriptions` (requires `DATABASE_ENABLED=true` and migrations up to version 2).
- Pipeline: In `MULTI_USER_MODE`, digests are filtered per user subscription (categories/keywords) and sent individually; falls back to single-recipient mode when no active users are found.

### Configuration System

[config.py](src/ai_mail_relay/config.py) uses frozen dataclasses for immutability:
- `ArxivConfig`: Fetching mode ("api" or "email") and API-specific settings (NEW)
- `MailboxConfig`: IMAP settings (kept for backward compatibility; not used in API-only mode)
- `OutboxConfig`: SMTP settings, recipient addresses, and connection parameters
  - `smtp_timeout`: Connection timeout in seconds (default: 30)
  - `smtp_retry_attempts`: Number of retry attempts on failure (default: 3)
  - `smtp_retry_base_delay`: Base delay in seconds for exponential backoff (default: 2.0)
- `FilteringConfig`: arXiv category/keyword filters and date range
- `LLMConfig`: LLM provider, model, API credentials, and request parameters
- `DatabaseConfig`: SQLite database path and enabled flag (NEW)
- `MultiUserConfig`: Multi-user subscription mode settings (NEW)
- `Settings`: Top-level container with `validate()` for required field checks

Environment variables are read via `os.getenv()` in field factories. Helper functions `_get_env_list()` and `_get_env_bool()` parse comma-separated lists and boolean values.

The `Settings.validate()` method enforces `ARXIV_FETCH_MODE=api` (email mode removed).

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

Email mode has been removed; parsing now relies solely on arXiv API responses handled in [arxiv_fetcher.py](src/ai_mail_relay/arxiv_fetcher.py).

## Development Notes

- The codebase uses Python 3.10+ type hints extensively (PEP 604 union syntax `X | Y`)
- All modules have `__all__` exports for clean public APIs
- Logging is done via standard library `logging` with module-level loggers
- No test suite currently exists (no `test_*.py` files found)
- Entry point is registered in [pyproject.toml](pyproject.toml:16) as `ai-mail-relay`
- Primary dependency is `httpx` for async-capable HTTP; no dependency on official OpenAI/Anthropic SDKs
- The application uses SQLite for persistent storage (database enabled by default)
- Papers are deduplicated across runs using the database (by arxiv_id)
- The application is now stateful: user/account data, subscriptions, delivery history, and papers live in SQLite; ensure migrations run before invoking user or multi-user commands

## Common Pitfalls

- **Provider endpoint configuration**: When adding support for a new provider or debugging API calls, note that providers auto-replace the OpenAI default endpoint. Check [llm_providers.py](src/ai_mail_relay/llm_providers.py) for endpoint construction logic.
- **Configuration validation**: Settings validation only happens in [main.py](src/ai_mail_relay/main.py:36) after `Settings()` construction. Missing required env vars will cause `ValueError` at startup.
- **Timezone handling**: Date filtering in [pipeline.py](src/ai_mail_relay/pipeline.py:102-118) uses UTC consistently.
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

## Database CLI Commands

```bash
# Initialize the database (creates tables, runs migrations)
ai-mail-relay db init

# Show database status (paper counts, date range)
ai-mail-relay db status

# Backup the database
ai-mail-relay db backup
ai-mail-relay db backup --output /path/to/backup.db
```

## Database Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `DATABASE_ENABLED` | Enable SQLite storage | `true` |
| `DATABASE_PATH` | Path to SQLite database file | `./data/ai_mail_relay.db` |
| `MULTI_USER_MODE` | Enable multi-user subscriptions | `false` |
| `SKIP_DELIVERED_PAPERS` | Skip papers already sent to user | `true` |
