"""CLI helpers for user management commands."""

from __future__ import annotations

import argparse
import logging
from typing import Iterable, List

from ..config import Settings


def _parse_csv(value: str | None) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def attach_user_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Register user-related subcommands."""
    user_parser = subparsers.add_parser("user", help="User management commands")
    user_subparsers = user_parser.add_subparsers(dest="user_command", help="User sub-commands")

    add_parser = user_subparsers.add_parser("add", help="Add a user")
    add_parser.add_argument("--email", required=True, help="User email (unique)")
    add_parser.add_argument("--name", help="Display name")

    list_parser = user_subparsers.add_parser("list", help="List all users")
    list_parser.add_argument("--all", action="store_true", help="Include inactive users")

    show_parser = user_subparsers.add_parser("show", help="Show details for a user")
    show_parser.add_argument("--email", required=True, help="User email")

    deactivate_parser = user_subparsers.add_parser("deactivate", help="Deactivate a user")
    deactivate_parser.add_argument("--email", required=True, help="User email")

    activate_parser = user_subparsers.add_parser("activate", help="Activate a user")
    activate_parser.add_argument("--email", required=True, help="User email")

    subscribe_parser = user_subparsers.add_parser("subscribe", help="Subscribe a user to categories/keywords")
    subscribe_parser.add_argument("--email", required=True, help="User email")
    subscribe_parser.add_argument("--categories", help="Comma-separated categories, e.g., cs.AI,cs.LG")
    subscribe_parser.add_argument("--keywords", help="Comma-separated keywords, e.g., transformer,LLM")

    unsubscribe_parser = user_subparsers.add_parser("unsubscribe", help="Remove subscriptions for a user")
    unsubscribe_parser.add_argument("--email", required=True, help="User email")
    unsubscribe_parser.add_argument("--categories", help="Comma-separated categories to remove")
    unsubscribe_parser.add_argument("--keywords", help="Comma-separated keywords to remove")

    subs_parser = user_subparsers.add_parser("subscriptions", help="List subscriptions for a user")
    subs_parser.add_argument("--email", required=True, help="User email")


def handle_user_command(args: argparse.Namespace, settings: Settings) -> int:
    """Dispatch user commands."""
    from ..database import init_database, run_migrations
    from ..services import UserService

    if not settings.database.enabled:
        logging.error("Database must be enabled for user commands (set DATABASE_ENABLED=true).")
        return 1

    init_database(settings.database)
    run_migrations()

    service = UserService()

    if args.user_command == "add":
        user = service.create_user(email=args.email, name=args.name)
        print(f"User created or already exists: {user.email} (active={user.is_active})")
        return 0

    if args.user_command == "list":
        users = service.list_users() if args.all else service.get_active_users()
        if not users:
            print("No users found.")
            return 0
        for user in users:
            status = "active" if user.is_active else "inactive"
            label = f"{user.name} <{user.email}>" if user.name else user.email
            print(f"- {label} [{status}]")
        return 0

    if args.user_command == "show":
        user = service.get_user(args.email)
        if not user:
            print(f"User not found: {args.email}")
            return 1
        subs = service.get_subscriptions(user)
        status = "active" if user.is_active else "inactive"
        print(f"Email: {user.email}")
        print(f"Name: {user.name or '(none)'}")
        print(f"Status: {status}")
        print(f"Categories: {', '.join(subs.categories) if subs.categories else '(none)'}")
        print(f"Keywords: {', '.join(subs.keywords) if subs.keywords else '(none)'}")
        return 0

    if args.user_command in {"deactivate", "activate"}:
        user = service.get_user(args.email)
        if not user:
            print(f"User not found: {args.email}")
            return 1
        enabled = args.user_command == "activate"
        updated = service.set_active(args.email, enabled)
        if updated:
            print(f"{'Activated' if enabled else 'Deactivated'} {args.email}")
            return 0
        print(f"No changes applied for {args.email}")
        return 0

    if args.user_command in {"subscribe", "unsubscribe"}:
        user = service.get_user(args.email)
        if not user:
            print(f"User not found: {args.email}")
            return 1

        categories = _parse_csv(getattr(args, "categories", None))
        keywords = _parse_csv(getattr(args, "keywords", None))
        if not categories and not keywords:
            print("No categories or keywords provided.")
            return 1

        if args.user_command == "subscribe":
            added = service.subscribe(user, categories=categories, keywords=keywords)
            print(f"Added {added} subscription(s) for {args.email}")
        else:
            removed = service.unsubscribe(user, categories=categories, keywords=keywords)
            print(f"Removed {removed} subscription(s) for {args.email}")
        return 0

    if args.user_command == "subscriptions":
        user = service.get_user(args.email)
        if not user:
            print(f"User not found: {args.email}")
            return 1
        subs = service.get_subscriptions(user)
        print(f"Categories: {', '.join(subs.categories) if subs.categories else '(none)'}")
        print(f"Keywords: {', '.join(subs.keywords) if subs.keywords else '(none)'}")
        return 0

    # Unknown or missing subcommand
    print("Missing user sub-command. Use --help for options.")
    return 1


__all__ = ["attach_user_subparser", "handle_user_command"]
