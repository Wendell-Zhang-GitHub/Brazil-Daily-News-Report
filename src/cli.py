"""argparse 入口"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .pipeline import run


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="巴西经贸信息周报生成系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例:
  python -m brazil_daily_news --start 2026-03-09 --end 2026-03-16
  python -m brazil_daily_news --start 2026-03-09 --end 2026-03-16 --steps scrape
  python -m brazil_daily_news --start 2026-03-09 --end 2026-03-16 --steps filter,report
  python -m brazil_daily_news --start 2026-03-09 --end 2026-03-16 --dry-run
""",
    )
    parser.add_argument("--start", required=True, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="结束日期 YYYY-MM-DD")
    parser.add_argument(
        "--steps",
        default="scrape,filter,report",
        help="运行步骤，逗号分隔 (scrape,filter,report)",
    )
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--force-scrape", action="store_true", help="强制重新抓取")
    parser.add_argument("--dry-run", action="store_true", help="只爬虫不调 AI")
    parser.add_argument("-v", "--verbose", action="store_true", help="详细日志")

    args = parser.parse_args()
    setup_logging(args.verbose)

    steps = [s.strip() for s in args.steps.split(",")]
    config_path = Path(args.config) if args.config else None

    result = run(
        start_date=args.start,
        end_date=args.end,
        steps=steps,
        config_path=config_path,
        force_scrape=args.force_scrape,
        dry_run=args.dry_run,
    )

    if result:
        print(f"\n报告已生成，长度 {len(result)} 字符")
