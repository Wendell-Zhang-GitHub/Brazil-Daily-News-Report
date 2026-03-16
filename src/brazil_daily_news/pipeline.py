"""编排：scrape → persist → filter → persist → report"""
from __future__ import annotations

import datetime as dt
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .config import ScrapedArticle, FilteredArticle, Source, load_config
from .scraper import get_scraper
from .scraper.http_client import HttpClient
from .storage import (
    save_raw_articles, load_raw_articles,
    save_filtered_articles, load_filtered_articles,
    save_report,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str], None] | None


def _scrape_one_source(
    source: Source,
    run_date: str,
    start_date: dt.date | None,
    end_date: dt.date | None,
    force: bool,
) -> list[ScrapedArticle]:
    """抓取单个源（在独立线程中运行，每个线程有自己的 HttpClient）"""
    if not force:
        cached = load_raw_articles(source.name, run_date)
        if cached is not None:
            logger.info("源 %s: 使用缓存 (%d 篇)", source.name, len(cached))
            return cached

    start = time.time()
    logger.info("开始抓取源: %s", source.name)

    try:
        client = HttpClient()  # 每个源独立 client，独立限速
        scraper_cls = get_scraper(source.parser)
        scraper = scraper_cls(client, source, start_date=start_date, end_date=end_date)
        articles = scraper.scrape()
    except Exception as exc:
        logger.error("源 %s 抓取失败: %s", source.name, exc)
        articles = []

    save_raw_articles(articles, source.name, run_date)
    logger.info(
        "源 %s 完成: %d 篇, 耗时 %.1fs",
        source.name, len(articles), time.time() - start,
    )
    return articles


def run_scrape(
    sources: list[Source],
    run_date: str,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    force: bool = False,
    progress_cb: ProgressCallback = None,
) -> list[ScrapedArticle]:
    """爬虫阶段：并发抓取所有源"""
    all_articles: list[ScrapedArticle] = []
    sorted_sources = sorted(sources, key=lambda s: (s.priority, s.name))

    if progress_cb:
        progress_cb(f"正在并发抓取 {len(sorted_sources)} 个新闻源...")

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(
                _scrape_one_source, source, run_date, start_date, end_date, force
            ): source
            for source in sorted_sources
        }
        done_count = 0
        for future in as_completed(futures):
            source = futures[future]
            done_count += 1
            try:
                articles = future.result()
                all_articles.extend(articles)
                if progress_cb:
                    progress_cb(
                        f"爬虫进度 ({done_count}/{len(sorted_sources)}): "
                        f"{source.name} 完成 ({len(articles)} 篇)"
                    )
            except Exception as exc:
                logger.error("源 %s 抓取异常: %s", source.name, exc)

    return all_articles


def run_filter(
    articles: list[ScrapedArticle],
    start_date: dt.date,
    end_date: dt.date,
    run_date: str,
    progress_cb: ProgressCallback = None,
) -> list[FilteredArticle]:
    """AI 过滤阶段"""
    from .ai.filter import filter_articles, get_relevant_articles

    # 二次日期过滤
    date_filtered = [
        a for a in articles
        if not a.published_date
        or (start_date <= a.published_date <= end_date)
    ]
    logger.info(
        "日期过滤: %d → %d 篇 (%s ~ %s)",
        len(articles), len(date_filtered), start_date, end_date,
    )

    if not date_filtered:
        logger.warning("无文章可过滤")
        save_filtered_articles([], run_date)
        return []

    if progress_cb:
        progress_cb(f"AI 并发过滤中 ({len(date_filtered)} 篇)...")

    # 并发过滤
    all_filtered = filter_articles(date_filtered, progress_cb=progress_cb)
    save_filtered_articles(all_filtered, run_date)

    relevant = get_relevant_articles(all_filtered)
    logger.info("AI 过滤: %d → %d 篇相关", len(all_filtered), len(relevant))
    return relevant


def run_report(
    articles: list[FilteredArticle],
    start_date: str,
    end_date: str,
    progress_cb: ProgressCallback = None,
) -> str:
    """报告生成阶段"""
    from .ai.reporter import generate_report

    if progress_cb:
        progress_cb("正在生成报告...")

    if not articles:
        logger.warning("无相关文章，生成空报告")
        report = (
            f"# 巴西经贸信息周报\n\n"
            f"统计区间：`{start_date}` 至 `{end_date}`\n\n"
            f"本周未检索到符合条件的经贸信息。\n"
        )
    else:
        report = generate_report(articles, start_date, end_date)

    save_report(report, start_date, end_date)
    return report


def run(
    start_date: str,
    end_date: str,
    steps: list[str] | None = None,
    config_path=None,
    force_scrape: bool = False,
    dry_run: bool = False,
    progress_callback: ProgressCallback = None,
) -> str | None:
    """完整 pipeline 运行"""
    all_steps = steps or ["scrape", "filter", "report"]
    start = dt.date.fromisoformat(start_date)
    end = dt.date.fromisoformat(end_date)
    run_date = end_date

    _, sources = load_config(config_path)

    # Step 1: Scrape
    if "scrape" in all_steps:
        articles = run_scrape(
            sources, run_date, start_date=start, end_date=end,
            force=force_scrape, progress_cb=progress_callback,
        )
        logger.info("爬虫完成: 共 %d 篇原始文章", len(articles))
    else:
        articles = []
        for source in sources:
            cached = load_raw_articles(source.name, run_date)
            if cached:
                articles.extend(cached)
        logger.info("从缓存加载: 共 %d 篇原始文章", len(articles))

    if dry_run:
        logger.info("Dry run 模式，跳过 AI 步骤")
        return None

    # Step 2: Filter
    if "filter" in all_steps:
        relevant = run_filter(articles, start, end, run_date, progress_cb=progress_callback)
    else:
        from .ai.filter import get_relevant_articles
        all_filtered = load_filtered_articles(run_date)
        if all_filtered:
            relevant = get_relevant_articles(all_filtered)
        else:
            relevant = []
        logger.info("从缓存加载: %d 篇相关文章", len(relevant))

    # Step 3: Report
    if "report" in all_steps:
        report = run_report(relevant, start_date, end_date, progress_cb=progress_callback)
        if progress_callback:
            progress_callback("报告生成完成！")
        return report

    return None
