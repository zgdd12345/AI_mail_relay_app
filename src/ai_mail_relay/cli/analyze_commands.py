"""CLI commands for analysis workflows (embeddings, clustering, trends)."""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from typing import Tuple

from ..services import AnalysisService


def _parse_date_range(raw: str) -> Tuple[date, date | None]:
    """Parse CLI date range values formatted as YYYY-MM-DD or start:end."""
    if ":" in raw:
        start_str, end_str = raw.split(":", 1)
    else:
        start_str, end_str = raw, ""

    try:
        start = datetime.fromisoformat(start_str).date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid start date: {start_str}") from exc

    end = None
    if end_str:
        try:
            end = datetime.fromisoformat(end_str).date()
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"Invalid end date: {end_str}") from exc
    return start, end


def attach_analyze_subparser(subparsers: argparse._SubParsersAction) -> None:
    analyze_parser = subparsers.add_parser("analyze", help="Run analysis: embeddings, clustering, trends")
    analyze_sub = analyze_parser.add_subparsers(dest="analyze_command", help="Analysis sub-commands")

    embed_parser = analyze_sub.add_parser("embed", help="Generate embeddings for a date range")
    embed_parser.add_argument(
        "--date-range",
        type=_parse_date_range,
        default=None,
        help="Date range (YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD). Default: today.",
    )
    embed_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate embeddings even if cached.",
    )

    cluster_parser = analyze_sub.add_parser("cluster", help="Cluster papers by field and embedding")
    cluster_parser.add_argument(
        "--date-range",
        type=_parse_date_range,
        default=None,
        help="Date range (YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD). Default: today.",
    )

    trend_parser = analyze_sub.add_parser("trend", help="Compute trend snapshot for a date range")
    trend_parser.add_argument(
        "--date-range",
        type=_parse_date_range,
        default=None,
        help="Date range (YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD). Default: today.",
    )
    trend_parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Trend aggregation period.",
    )

    report_parser = analyze_sub.add_parser("report", help="Generate a Markdown report (clusters + trends)")
    report_parser.add_argument(
        "--date-range",
        type=_parse_date_range,
        default=None,
        help="Date range (YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD). Default: today.",
    )
    report_parser.add_argument(
        "--output",
        type=str,
        help="Output file path. Default: {ANALYSIS_REPORT_DIR}/report-<date>.<ext>",
    )
    report_parser.add_argument(
        "--format",
        choices=["markdown", "html", "json"],
        default=None,
        help="Report format. Default comes from ANALYSIS_REPORT_FORMAT.",
    )


def _resolve_range(arg_value) -> tuple[date, date | None]:
    if arg_value is None:
        today = date.today()
        return today, None
    return arg_value


def handle_analyze_command(args, settings) -> int:
    service = AnalysisService(settings)
    start_date, end_date = _resolve_range(getattr(args, "date_range", None))

    try:
        if args.analyze_command == "embed":
            count = service.generate_embeddings(start_date, end_date=end_date, force=args.force)
            print(f"Embedding generation complete. New embeddings: {count}.")
            return 0

        if args.analyze_command == "cluster":
            run_id, cluster_records, _ = service.run_clustering(start_date, end_date=end_date)
            print(f"Clustering complete. Run ID: {run_id}. Clusters: {len(cluster_records)}.")
            return 0

        if args.analyze_command == "trend":
            result = service.run_trend_analysis(start_date, end_date=end_date, period_type=args.period)
            print(f"Trend snapshot stored for {result.snapshot_date} ({result.period_type}).")
            if result.previous_snapshot_date:
                print(f"Compared against snapshot dated {result.previous_snapshot_date}.")
            for field, count in sorted(result.field_trends.items(), key=lambda kv: kv[1], reverse=True):
                print(f"- {field}: {count}")
            if result.hot_topics:
                print(f"Hot topics: {', '.join(result.hot_topics)}")
            if result.emerging_topics:
                print(f"Rising: {', '.join(result.emerging_topics)}")
            if result.declining_topics:
                print(f"Declining: {', '.join(result.declining_topics)}")
            return 0

        if args.analyze_command == "report":
            run_id, cluster_records, clusters = service.run_clustering(start_date, end_date=end_date)
            trend = service.run_trend_analysis(start_date, end_date=end_date, period_type="daily")
            total_papers = len({pid for cluster in clusters for pid in cluster.paper_ids})
            report_format = (args.format or settings.analysis.analysis_report_format).lower()

            if args.output:
                output_path = Path(args.output)
            else:
                extension = {"markdown": "md", "html": "html", "json": "json"}.get(report_format, "md")
                report_dir = Path(settings.analysis.analysis_report_dir)
                report_dir.mkdir(parents=True, exist_ok=True)
                output_path = report_dir / f"report-{start_date.isoformat()}.{extension}"

            service.generate_report(
                clusters=clusters,
                trend=trend,
                total_papers=total_papers,
                output_path=output_path,
                fmt=report_format,
                cluster_records=cluster_records,
            )
            print(f"Report written to {output_path} (cluster run {run_id}, format={report_format}).")
            return 0
    except Exception as exc:  # pragma: no cover - CLI error surface
        print(f"[analyze] error: {exc}")
        return 1

    analyze_help = args.parser if hasattr(args, "parser") else None
    if analyze_help:
        analyze_help.print_help()
    else:
        print("Unknown analyze command. Use --help for available options.")
    return 1
