#!/usr/bin/env python3
"""Unified test script for AI Mail Relay application.

Usage:
    python test.py              # Full test with 3 papers
    python test.py --mode api   # Test API mode only
    python test.py --mode email # Test email mode only
    python test.py --no-llm     # Skip LLM summarization (fast test)
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from src.ai_mail_relay.config import Settings
from src.ai_mail_relay.llm_client import LLMClient
from src.ai_mail_relay.mail_sender import MailSender
from src.ai_mail_relay.pipeline import fetch_from_api, fetch_from_email
from src.ai_mail_relay.arxiv_parser import filter_papers


async def test_api_mode(settings: Settings, max_papers: int = 3) -> None:
    """Test API mode fetching."""
    print("\n" + "=" * 60)
    print("测试 API 模式")
    print("=" * 60)

    papers = fetch_from_api(settings)
    print(f"获取到 {len(papers)} 篇论文")

    if not papers:
        print("⚠️  没有获取到论文")
        return []

    # Filter
    filtered = filter_papers(
        papers,
        settings.filtering.allowed_categories,
        settings.filtering.keyword_filters
    )
    print(f"过滤后: {len(filtered)} 篇 AI 相关论文")

    # Limit for testing
    test_papers = filtered[:max_papers]

    print(f"\n测试论文列表 (前 {len(test_papers)} 篇):")
    for i, paper in enumerate(test_papers, 1):
        print(f"  {i}. {paper.title[:70]}")
        print(f"     类别: {paper.categories[:3]}")

    return test_papers


async def test_email_mode(settings: Settings, max_papers: int = 3) -> None:
    """Test email mode fetching."""
    print("\n" + "=" * 60)
    print("测试邮箱模式")
    print("=" * 60)

    papers = fetch_from_email(settings)
    print(f"从邮箱获取到 {len(papers)} 篇论文")

    if not papers:
        print("⚠️  没有获取到论文（可能邮箱中没有未读邮件）")
        return []

    # Filter
    filtered = filter_papers(
        papers,
        settings.filtering.allowed_categories,
        settings.filtering.keyword_filters
    )
    print(f"过滤后: {len(filtered)} 篇 AI 相关论文")

    # Limit for testing
    test_papers = filtered[:max_papers]

    print(f"\n测试论文列表 (前 {len(test_papers)} 篇):")
    for i, paper in enumerate(test_papers, 1):
        print(f"  {i}. {paper.title[:70]}")
        print(f"     类别: {paper.categories[:3]}")

    return test_papers


async def test_llm_summarization(settings: Settings, papers: list) -> str:
    """Test LLM summarization."""
    if not papers:
        return ""

    print("\n" + "=" * 60)
    print(f"测试 LLM 摘要生成 (并发数: {settings.llm.max_concurrent_requests})")
    print("=" * 60)

    llm_client = LLMClient(settings.llm)
    summary = await llm_client.summarize_papers(papers)

    print("\n生成的摘要预览 (前 300 字):")
    print("-" * 60)
    print(summary[:300])
    print("...")

    return summary


async def test_email_sending(settings: Settings, summary: str, papers: list) -> None:
    """Test email sending."""
    if not papers or not summary:
        print("\n跳过邮件发送测试（没有论文或摘要）")
        return

    print("\n" + "=" * 60)
    print("测试邮件发送")
    print("=" * 60)

    sender = MailSender(settings.outbox)
    sender.send_digest(summary, papers)

    print("✅ 邮件发送成功！请检查收件箱。")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Test AI Mail Relay")
    parser.add_argument(
        "--mode",
        choices=["api", "email", "both"],
        default="api",
        help="Test mode (default: api)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM summarization (faster)"
    )
    parser.add_argument(
        "--no-email",
        action="store_true",
        help="Skip email sending"
    )
    parser.add_argument(
        "--papers",
        type=int,
        default=3,
        help="Number of papers to test (default: 3)"
    )

    args = parser.parse_args()

    # Load configuration
    load_dotenv()
    settings = Settings()

    print("=" * 60)
    print("AI Mail Relay 测试脚本")
    print("=" * 60)
    print(f"测试模式: {args.mode}")
    print(f"测试论文数: {args.papers}")
    print(f"LLM 提供商: {settings.llm.provider}")
    print(f"LLM 并发数: {settings.llm.max_concurrent_requests}")

    try:
        settings.validate()
        print("✅ 配置验证通过")
    except Exception as e:
        print(f"❌ 配置验证失败: {e}")
        sys.exit(1)

    # Test paper fetching
    papers = []

    if args.mode in ["api", "both"]:
        papers = await test_api_mode(settings, args.papers)

    if args.mode in ["email", "both"] and not papers:
        papers = await test_email_mode(settings, args.papers)

    if not papers:
        print("\n❌ 未获取到论文，测试结束")
        return

    # Test LLM summarization
    summary = ""
    if not args.no_llm:
        summary = await test_llm_summarization(settings, papers)
    else:
        print("\n⏭️  跳过 LLM 摘要生成")
        summary = "Test summary (LLM skipped)"

    # Test email sending
    if not args.no_email:
        await test_email_sending(settings, summary, papers)
    else:
        print("\n⏭️  跳过邮件发送")

    print("\n" + "=" * 60)
    print("✅ 所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
