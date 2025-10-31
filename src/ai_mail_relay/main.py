"""CLI entry-point for the AI mail relay app."""

from __future__ import annotations

import argparse
import logging
import sys
import asyncio

from dotenv import load_dotenv

from .config import Settings
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch unread arXiv emails, summarize with an LLM, and forward the digest."
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging verbosity",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    # Load environment variables from .env file
    load_dotenv()

    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    settings = Settings()
    try:
        settings.validate()
    except ValueError as exc:
        logging.error("Configuration error: %s", exc)
        return 1

    try:
        asyncio.run(run_pipeline(settings))
    except Exception:  # pragma: no cover - top-level guard
        logging.exception("Failed to complete mail relay run")
        return 1

    logging.info("Mail relay run completed successfully")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
