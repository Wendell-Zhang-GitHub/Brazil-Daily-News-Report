"""AI 过滤：粗筛（Gemini Lite 200并发）+ 深度评分（Gemini Flash 逐篇并发）"""
from __future__ import annotations

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from ..config import ScrapedArticle, FilteredArticle
from .client import call_filter, call_deep_filter, FILTER_MAX_CONCURRENCY
from .prompts import (
    FILTER_SYSTEM, FILTER_USER_TEMPLATE,
    DEEP_FILTER_SYSTEM, DEEP_FILTER_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)

_done_counter_lock = threading.Lock()

MAX_FINAL_ARTICLES = 6


def _extract_json(text: str) -> dict:
    """从可能包含 markdown 代码块的响应中提取 JSON"""
    text = text.strip()
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


# ── 第一层：粗筛 ─────────────────────────────────────────

def filter_article(article: ScrapedArticle) -> FilteredArticle:
    """用 Gemini Lite 判断单篇文章的相关性"""
    body_preview = article.body[:500] if article.body else ""

    user_content = FILTER_USER_TEMPLATE.format(
        source_name=article.source_name,
        title=article.title,
        body_preview=body_preview,
    )

    try:
        response_text = call_filter(FILTER_SYSTEM, user_content)
        result = _extract_json(response_text)
        is_relevant = result.get("is_relevant", False)
        confidence = float(result.get("confidence", 0.0))
        category = result.get("category", "不相关")
        reason = result.get("reason", "")
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("粗筛解析失败 [%s]: %s", article.title, e)
        is_relevant = False
        confidence = 0.0
        category = "解析错误"
        reason = str(e)

    return FilteredArticle(
        source_name=article.source_name,
        source_category=article.source_category,
        source_country=article.source_country,
        title=article.title,
        url=article.url,
        published_at=article.published_at,
        body=article.body,
        is_relevant=is_relevant,
        confidence=confidence,
        category=category,
        reason=reason,
        source_officiality=article.source_officiality,
        source_credibility=article.source_credibility,
    )


def filter_articles(
    articles: list[ScrapedArticle],
    progress_cb: Callable[[str], None] | None = None,
) -> list[FilteredArticle]:
    """第一层：并发粗筛所有文章（并发数 = min(文章数, GEMINI_CONCURRENCY)）"""
    total = len(articles)
    max_workers = min(total, FILTER_MAX_CONCURRENCY)
    logger.info("粗筛并发数: %d（文章 %d 篇，上限 %d）", max_workers, total, FILTER_MAX_CONCURRENCY)
    results: list[FilteredArticle] = [None] * total
    done_count = 0

    def _process(idx: int, article: ScrapedArticle) -> tuple[int, FilteredArticle]:
        return idx, filter_article(article)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_process, i, a): i
            for i, a in enumerate(articles)
        }
        for future in as_completed(futures):
            try:
                idx, result = future.result()
                results[idx] = result
                with _done_counter_lock:
                    done_count += 1
                    current = done_count
                status = "✓ 相关" if result.is_relevant else "✗"
                logger.info(
                    "粗筛 [%d/%d]: %s %s",
                    current, total, status, result.title[:50],
                )
                if progress_cb and current % 5 == 0:
                    progress_cb(f"粗筛进度 ({current}/{total})...")
            except Exception as exc:
                logger.error("粗筛任务异常: %s", exc)

    if progress_cb:
        progress_cb(f"粗筛完成 ({total}/{total})")

    return [r for r in results if r is not None]


def get_relevant_articles(
    filtered: list[FilteredArticle], min_confidence: float = 0.6
) -> list[FilteredArticle]:
    """筛选出相关且置信度达标的文章"""
    return [
        a for a in filtered
        if a.is_relevant and a.confidence >= min_confidence
    ]


# ── 第二层：深度评分 ──────────────────────────────────────

def _score_one_article(article: FilteredArticle) -> tuple[FilteredArticle, int]:
    """对单篇文章独立评分 0-100"""
    body_preview = article.body[:800] if article.body else "(无正文)"

    user_content = DEEP_FILTER_USER_TEMPLATE.format(
        source_name=article.source_name,
        source_category=article.source_category,
        source_country=article.source_country,
        source_officiality=article.source_officiality,
        source_credibility=article.source_credibility,
        title=article.title,
        published_at=article.published_at or "未知",
        category=article.category,
        confidence=article.confidence,
        body_preview=body_preview,
    )

    try:
        response_text = call_deep_filter(DEEP_FILTER_SYSTEM, user_content)
        result = _extract_json(response_text)
        score = int(result.get("score", 0))
        reason = result.get("reason", "")
        logger.info(
            "深度评分: %d 分 | %s | %s",
            score, article.title[:50], reason[:60],
        )
        return article, score
    except Exception as e:
        logger.warning("深度评分失败 [%s]: %s", article.title[:50], e)
        return article, 0


def deep_select_articles(
    articles: list[FilteredArticle],
    progress_cb: Callable[[str], None] | None = None,
    max_articles: int = MAX_FINAL_ARTICLES,
) -> list[FilteredArticle]:
    """第二层：Gemini Flash 逐篇独立评分，取前N篇"""
    if len(articles) <= max_articles:
        logger.info("粗筛结果 %d 篇，不超过 %d，跳过深度筛选", len(articles), max_articles)
        return articles

    if progress_cb:
        progress_cb(f"深度评分中（{len(articles)} 篇逐篇打分）...")

    total = len(articles)
    scored: list[tuple[FilteredArticle, int]] = []
    done_count = 0

    with ThreadPoolExecutor(max_workers=total) as pool:
        futures = {
            pool.submit(_score_one_article, a): a
            for a in articles
        }
        for future in as_completed(futures):
            try:
                article, score = future.result()
                scored.append((article, score))
                with _done_counter_lock:
                    done_count += 1
                    current = done_count
                if progress_cb and current % 3 == 0:
                    progress_cb(f"深度评分 ({current}/{total})...")
            except Exception as exc:
                logger.error("深度评分任务异常: %s", exc)

    # 按分数降序，取前6
    scored.sort(key=lambda x: x[1], reverse=True)

    selected = [a for a, s in scored[:max_articles]]
    scores_log = [(a.title[:40], s) for a, s in scored[:max_articles]]
    logger.info("深度筛选结果（前%d）: %s", max_articles, scores_log)

    if progress_cb:
        progress_cb(f"深度筛选完成，精选 {len(selected)} 篇（最高分 {scored[0][1]}）")

    return selected
