"""SMTP helpers for forwarding digests."""

from __future__ import annotations

import logging
import re
import smtplib
import socket
import time
from email.message import EmailMessage
from typing import List

from .arxiv_parser import ArxivPaper
from .config import OutboxConfig, today_string


LOGGER = logging.getLogger(__name__)


class MailSender:
    """Send digest emails via SMTP."""

    def __init__(self, config: OutboxConfig) -> None:
        self._config = config

    def send_digest(
        self,
        summary_md: str,
        papers: List[ArxivPaper],
        report_date: str | None = None,
    ) -> None:
        """Compose and send the digest email."""
        if report_date is None:
            report_date = today_string()

        message = EmailMessage()
        message["From"] = self._config.from_address
        message["To"] = self._config.to_address
        message["Subject"] = f"📚 arXiv AI 论文摘要 — {report_date} ({len(papers)}篇)"
        message.set_content(
            f"每日 arXiv AI 论文摘要（共 {len(papers)} 篇）\n\n"
            "请在支持 HTML 的邮件客户端中查看完整格式。\n"
            "附件包含所有论文的基本信息和原始摘要。\n"
        )
        message.add_alternative(self._build_body_with_papers(summary_md, papers), subtype="html")

        attachment_content = self._build_attachment(summary_md, papers)
        filename = f"arxiv_ai_digest_{report_date}.md"
        message.add_attachment(
            attachment_content.encode("utf-8"),
            maintype="text",
            subtype="markdown",
            filename=filename,
        )

        LOGGER.info("Sending digest email with %d papers", len(papers))
        self._send(message)

    def _send(self, message: EmailMessage) -> None:
        """Send email with retry logic and timeout handling."""
        last_exception = None

        for attempt in range(self._config.smtp_retry_attempts + 1):
            try:
                if self._config.use_tls:
                    with smtplib.SMTP(
                        self._config.smtp_host,
                        self._config.smtp_port,
                        timeout=self._config.smtp_timeout
                    ) as smtp:
                        smtp.starttls()
                        smtp.login(self._config.smtp_user, self._config.smtp_password)
                        smtp.send_message(message)
                else:
                    with smtplib.SMTP_SSL(
                        self._config.smtp_host,
                        self._config.smtp_port,
                        timeout=self._config.smtp_timeout
                    ) as smtp:
                        smtp.login(self._config.smtp_user, self._config.smtp_password)
                        smtp.send_message(message)

                # Success - log and return
                if attempt > 0:
                    LOGGER.info("Email sent successfully after %d retry attempts", attempt)
                else:
                    LOGGER.info("Email sent successfully")
                return

            except (socket.timeout, TimeoutError) as e:
                last_exception = e
                LOGGER.warning(
                    "SMTP connection timeout (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.smtp_retry_attempts + 1,
                    str(e)
                )
            except smtplib.SMTPAuthenticationError as e:
                # Don't retry authentication errors
                LOGGER.error("SMTP authentication failed: %s", str(e))
                raise
            except smtplib.SMTPException as e:
                last_exception = e
                LOGGER.warning(
                    "SMTP error (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.smtp_retry_attempts + 1,
                    str(e)
                )
            except OSError as e:
                last_exception = e
                LOGGER.warning(
                    "Network error (attempt %d/%d): %s",
                    attempt + 1,
                    self._config.smtp_retry_attempts + 1,
                    str(e)
                )

            # Don't sleep after the last attempt
            if attempt < self._config.smtp_retry_attempts:
                delay = self._config.smtp_retry_base_delay * (2 ** attempt)
                LOGGER.info("Retrying in %.1f seconds...", delay)
                time.sleep(delay)

        # All retries exhausted
        LOGGER.error(
            "Failed to send email after %d attempts. Last error: %s",
            self._config.smtp_retry_attempts + 1,
            str(last_exception)
        )
        raise last_exception

    def _build_body_with_papers(self, summary_md: str, papers: List[ArxivPaper]) -> str:
        """Build HTML email body with paper info and AI summaries integrated."""
        # Parse AI summaries by paper
        paper_summaries = self._parse_summaries_by_paper(summary_md, len(papers))

        # Build integrated papers section
        papers_html = ""
        for idx, paper in enumerate(papers, start=1):
            arxiv_link = paper.links[0] if paper.links else f"https://arxiv.org/abs/{paper.arxiv_id}"
            paper_summary = paper_summaries.get(idx, "暂无AI摘要")

            papers_html += f"""
    <div class="paper-card">
      <div class="paper-header">
        <span class="paper-number">论文 {idx}</span>
        <span class="separator">|</span>
        <span class="paper-title">{self._escape_html(paper.title)}</span>
      </div>

      <div class="core-info">
        {'<div class="work-summary">💡 ' + self._escape_html(paper.summary or '正在生成工作内容摘要...') + '</div>' if paper.summary else ''}
        {'<div class="research-field">📍 ' + self._escape_html(paper.research_field) + '</div>' if paper.research_field else ''}
      </div>

      <details class="basic-info">
        <summary class="info-header">
          <span class="info-title">📋 基本信息</span>
          <span class="toggle-hint">(点击展开/收起)</span>
        </summary>
        <div class="info-content">
          <div class="info-row">
            <span class="info-label">arXiv ID:</span>
            <span class="info-value">{self._escape_html(paper.arxiv_id or 'N/A')}</span>
          </div>
          <div class="info-row">
            <span class="info-label">作者:</span>
            <span class="info-value">{self._escape_html(paper.authors or 'Unknown')}</span>
          </div>
          {'<div class="info-row"><span class="info-label">单位/备注:</span><span class="info-value">' + self._escape_html(paper.affiliations) + '</span></div>' if paper.affiliations else ''}
          <div class="info-row">
            <span class="info-label">研究领域:</span>
            <span class="info-value">{self._escape_html(', '.join(paper.categories) or 'Unspecified')}</span>
          </div>
          <div class="info-row">
            <span class="info-label">论文链接:</span>
            <span class="info-value"><a href="{arxiv_link}" class="paper-link">{arxiv_link}</a></span>
          </div>
        </div>
      </details>

      <details class="ai-summary">
        <summary class="summary-header">
          <span class="summary-title">🤖 AI 详细摘要</span>
          <span class="toggle-hint">(点击展开/收起)</span>
        </summary>
        <div class="summary-content">
          {self._markdown_to_html(paper_summary)}
        </div>
      </details>
    </div>
"""

        return f"""\
<html>
  <head>
    <meta charset="UTF-8">
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f6f8; }}
      .container {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
      h1 {{ color: #1a1a1a; font-size: 28px; margin-bottom: 10px; }}
      .subtitle {{ color: #666; font-size: 14px; margin-bottom: 25px; }}
      .notice {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
      .notice strong {{ color: #fff; }}

      .paper-card {{ background: #fff; border: 1px solid #e1e4e8; border-radius: 8px; margin-bottom: 30px; overflow: hidden; transition: box-shadow 0.3s; }}
      .paper-card:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}

      .paper-header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; color: white; display: flex; align-items: center; gap: 12px; }}
      .paper-number {{ font-size: 14px; font-weight: 600; opacity: 0.9; flex-shrink: 0; }}
      .separator {{ font-size: 14px; opacity: 0.6; flex-shrink: 0; }}
      .paper-title {{ font-size: 18px; font-weight: 600; line-height: 1.4; flex: 1; }}

      .core-info {{ padding: 20px; background: white; }}
      .work-summary {{ background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #2c3e50; padding: 15px; border-radius: 6px; margin-bottom: 12px; font-size: 15px; line-height: 1.6; font-weight: 500; border-left: 4px solid #667eea; }}
      .research-field {{ background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #2c3e50; padding: 15px; border-radius: 6px; font-size: 14px; line-height: 1.6; font-weight: 500; border-left: 4px solid #667eea; }}

      .basic-info {{ padding: 0 20px 20px 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 8px; }}
      .basic-info summary {{ list-style: none; }}
      .basic-info summary::-webkit-details-marker {{ display: none; }}

      .info-header {{ cursor: pointer; padding: 15px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #2c3e50; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; user-select: none; transition: all 0.3s; border: 1px solid rgba(102, 126, 234, 0.25); }}
      .info-header:hover {{ transform: translateY(-2px); box-shadow: 0 4px 8px rgba(102, 126, 234, 0.25); }}

      .info-title {{ font-size: 16px; font-weight: 600; }}

      .basic-info[open] .info-header {{ border-radius: 6px 6px 0 0; }}

      .info-content {{ padding: 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 0 0 6px 6px; margin-top: -1px; }}
      .info-row {{ display: flex; margin-bottom: 10px; font-size: 14px; }}
      .info-row:last-child {{ margin-bottom: 0; }}
      .info-label {{ font-weight: 600; color: #495057; min-width: 100px; flex-shrink: 0; }}
      .info-value {{ color: #212529; flex: 1; }}
      .paper-link {{ color: #667eea; text-decoration: none; font-weight: 500; }}
      .paper-link:hover {{ text-decoration: underline; }}

      .ai-summary {{ padding: 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 8px; border-top: 1px solid rgba(103, 126, 234, 0.25); }}
      .ai-summary summary {{ list-style: none; }}
      .ai-summary summary::-webkit-details-marker {{ display: none; }}

      .summary-header {{ cursor: pointer; padding: 15px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); color: #2c3e50; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; user-select: none; transition: all 0.3s; border: 1px solid rgba(102, 126, 234, 0.25); }}
      .summary-header:hover {{ transform: translateY(-2px); box-shadow: 0 4px 8px rgba(102, 126, 234, 0.25); }}

      .summary-title {{ font-size: 16px; font-weight: 600; }}
      .toggle-hint {{ font-size: 12px; opacity: 0.9; font-weight: 400; }}

      .ai-summary[open] .summary-header {{ border-radius: 6px 6px 0 0; }}

      .summary-content {{ color: #333; line-height: 1.8; padding: 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 0 0 6px 6px; margin-top: -1px; }}
      .summary-content p {{ margin: 12px 0; }}
      .summary-content strong {{ color: #1a1a1a; font-weight: 600; }}
      .summary-content h3 {{ display: none; }}
      .summary-content h4 {{ display: none; }}
    </style>
  </head>
  <body>
    <div class="container">
      <h1>📚 每日 arXiv AI 论文摘要</h1>
      <div class="subtitle">精选 AI 领域最新研究，由人工智能自动摘要</div>

      <div class="notice">
        本期包含 <strong>{len(papers)}</strong> 篇论文<br>
        每篇论文包含：基本信息 + AI生成的结构化摘要（研究背景、方法、创新点、实验结果、结论）<br>
        附件包含所有论文的原始英文摘要（Markdown格式）
      </div>

      {papers_html}
    </div>
  </body>
</html>
"""

    def _build_attachment(self, summary_md: str, papers: List[ArxivPaper]) -> str:
        """Build attachment with basic info and original abstracts."""
        lines = ["# 每日 arXiv AI 论文摘要", ""]
        lines.append(f"共 {len(papers)} 篇论文")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")

        if papers:
            for idx, paper in enumerate(papers, start=1):
                lines.append(f"## 论文 {idx}: {paper.title}")
                lines.append("")
                lines.append("### 基本信息")
                lines.append(f"- **arXiv ID**: {paper.arxiv_id or 'N/A'}")
                lines.append(f"- **作者**: {paper.authors or 'Unknown'}")
                if paper.affiliations:
                    lines.append(f"- **单位/备注**: {paper.affiliations}")
                lines.append(f"- **研究领域**: {', '.join(paper.categories) or 'Unspecified'}")
                if paper.links:
                    lines.append(f"- **链接**: {paper.links[0] if paper.links else 'N/A'}")
                lines.append("")
                lines.append("### 原始摘要")
                lines.append(paper.abstract or "No abstract available.")
                lines.append("")
                lines.append("-" * 80)
                lines.append("")
        else:
            lines.append("未检测到相关AI论文。")

        return "\n".join(lines)

    @staticmethod
    def _escape_html(content: str) -> str:
        return (
            content.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def _parse_summaries_by_paper(self, summary_md: str, num_papers: int) -> dict:
        """Parse AI summaries and map them to paper numbers."""
        summaries = {}

        # Split by paper headers (e.g., "## Paper 1:", "## Paper 2:")
        pattern = r'## Paper (\d+):'
        parts = re.split(pattern, summary_md)

        # parts[0] is content before first paper (usually empty)
        # parts[1] is "1", parts[2] is content for paper 1
        # parts[3] is "2", parts[4] is content for paper 2, etc.
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                paper_num = int(parts[i])
                content = parts[i + 1].strip()
                summaries[paper_num] = content

        return summaries

    def _markdown_to_html(self, md_text: str) -> str:
        """Simple Markdown to HTML conversion for email display."""
        html = self._escape_html(md_text)

        # Convert headers
        html = re.sub(r'^### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)

        # Convert bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

        # Convert line breaks to paragraphs
        paragraphs = html.split('\n\n')
        html = ''.join(f'<p>{p.replace(chr(10), "<br>")}</p>' for p in paragraphs if p.strip())

        return html


__all__ = ["MailSender"]
