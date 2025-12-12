"""CLI entry-point for the AI mail relay app."""

from __future__ import annotations

import argparse
import asyncio
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from .config import Settings
from .cli.analyze_commands import attach_analyze_subparser, handle_analyze_command
from .cli.user_commands import attach_user_subparser, handle_user_command


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

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # db init command
    db_parser = subparsers.add_parser("db", help="Database management commands")
    db_subparsers = db_parser.add_subparsers(dest="db_command", help="Database sub-commands")

    db_subparsers.add_parser("init", help="Initialize the database")
    db_subparsers.add_parser("status", help="Show database status")

    backup_parser = db_subparsers.add_parser("backup", help="Backup the database")
    backup_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output path for backup file (default: ./data/backups/)",
    )

    # user management commands
    attach_user_subparser(subparsers)
    attach_analyze_subparser(subparsers)

    return parser


def cmd_db_init(settings: Settings) -> int:
    """Initialize the database and run migrations."""
    from .database import init_database, run_migrations, get_current_version

    if not settings.database.enabled:
        logging.error("Database is disabled. Set DATABASE_ENABLED=true to enable.")
        return 1

    init_database(settings.database)
    applied = run_migrations()

    if applied > 0:
        logging.info("Database initialized with %d migration(s)", applied)
    else:
        logging.info("Database already up to date (version %d)", get_current_version())

    return 0


def cmd_db_status(settings: Settings) -> int:
    """Show database status and statistics."""
    from .database import init_database, get_current_version
    from .services import PaperService

    if not settings.database.enabled:
        logging.error("Database is disabled. Set DATABASE_ENABLED=true to enable.")
        return 1

    db_path = Path(settings.database.path)
    if not db_path.exists():
        print(f"Database file: {db_path} (not created yet)")
        print("Run 'ai-mail-relay db init' to initialize the database.")
        return 0

    init_database(settings.database)

    stats = PaperService().get_stats()
    version = get_current_version()

    print(f"Database file: {db_path}")
    print(f"Schema version: {version}")
    print(f"Total papers: {stats['total_papers']}")
    print(f"Processed papers: {stats['processed_papers']}")
    print(f"Unprocessed papers: {stats['unprocessed_papers']}")
    if stats['earliest_date']:
        print(f"Date range: {stats['earliest_date']} to {stats['latest_date']}")

    return 0


def cmd_db_backup(settings: Settings, output: str | None = None) -> int:
    """Backup the database to a file."""
    if not settings.database.enabled:
        logging.error("Database is disabled. Set DATABASE_ENABLED=true to enable.")
        return 1

    db_path = Path(settings.database.path)
    if not db_path.exists():
        logging.error("Database file not found: %s", db_path)
        return 1

    if output:
        backup_path = Path(output)
    else:
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"ai_mail_relay_{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    print(f"Database backed up to: {backup_path}")

    return 0


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

    # Handle db subcommands (don't require full validation)
    if args.command == "db":
        if args.db_command == "init":
            return cmd_db_init(settings)
        elif args.db_command == "status":
            return cmd_db_status(settings)
        elif args.db_command == "backup":
            return cmd_db_backup(settings, args.output)
        else:
            parser.parse_args(["db", "--help"])
            return 1
    elif args.command == "user":
        return handle_user_command(args, settings)
    elif args.command == "analyze":
        return handle_analyze_command(args, settings)

    # Default: run the pipeline
    try:
        settings.validate()
    except ValueError as exc:
        logging.error("Configuration error: %s", exc)
        return 1

    try:
        from .pipeline import run_pipeline

        asyncio.run(run_pipeline(settings))
    except Exception:  # pragma: no cover - top-level guard
        logging.exception("Failed to complete mail relay run")
        return 1

    logging.info("Mail relay run completed successfully")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
