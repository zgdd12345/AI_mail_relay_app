# Repository Guidelines

## Project Structure & Module Organization
- Core code lives in `src/ai_mail_relay/`: `pipeline.py` orchestrates fetching, parsing, LLM summarization, and SMTP delivery; `arxiv_fetcher.py` and `mail_fetcher.py` handle input modes; `llm_client.py`/`llm_providers.py` wrap model APIs; `mail_sender.py` sends digests; `database/`, `repositories/`, and `services/` manage SQLite persistence/deduplication.
- CLI entrypoint: `ai-mail-relay` (`pyproject.toml` `[project.scripts]`); module entry: `python -m ai_mail_relay.main`.
- `docs/` holds user/deployment guides; `deploy/` contains automation scripts (cron setup, diagnostics); `data/` stores the default SQLite DB (`data/ai_mail_relay.db`); `logs/` is safe for local logs and should stay untracked.

## Build, Test, and Development Commands
- Install editable: `pip install -e .` (or `pip install -e ".[dev]"` when dev extras are added).
- Run locally with debug logs: `ai-mail-relay --log-level DEBUG`; database helpers: `ai-mail-relay db init|status|backup`.
- Smoke test the end-to-end flow (requires `.env`): `python test.py --mode api --papers 2`; email mode: `python test.py --mode email --no-llm`.
- Deployment diagnostics: `./deploy/diagnose.sh` (SMTP/port checks) and `./deploy/verify_api_mode.sh` for API fetch sanity.

## Coding Style & Naming Conventions
- Python 3.10+ with type hints; prefer frozen dataclasses for config (see `config.py`).
- Indentation 4 spaces; use `snake_case` for modules/functions/variables and `PascalCase` for classes.
- Keep module-level loggers (`logging.getLogger(__name__)`) and avoid broad `except:`. New features belong under `src/ai_mail_relay/` with clear boundaries (fetching/parsing/LLM/mail/db layers).

## Testing Guidelines
- Existing coverage is manual via `test.py`; add new tests under `tests/` with `test_*.py` naming. Pytest is recommended if expanded.
- When touching async or rate-limited code, include fixtures/mocks for HTTP and SMTP to avoid live calls. Document required env vars in the test docstring.

## Commit & Pull Request Guidelines
- Follow the current log style: short, imperative summaries (e.g., `add arxiv api`, `setup cron task`); keep scope focused.
- PRs should state problem/approach, config additions, and manual test commands run (paste relevant log snippets). Link related issues/plan items and add screenshots when UI/outputs change (e.g., email preview).

## Security & Configuration Notes
- Store secrets in `.env`; never commit API keys or SMTP/IMAP creds. Mask values in logs and PRs.
- The SQLite file in `data/` and any attachments in outbound emails may contain user info—exclude them from commits and sanitize when sharing samples.
