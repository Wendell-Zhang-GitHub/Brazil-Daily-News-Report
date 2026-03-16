"""Gemini 相关性过滤（支持高并发）"""
from __future__ import annotations

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from ..config import ScrapedArticle, FilteredArticle
from .client import call_filter
from .prompts import FILTER_SYSTEM, FILTER_USER_TEMPLATE

logger = logging.getLogger(__name__)

_done_counter_lock = threading.Lock()


def _extract_json(text: str) -> dict:
    """从可能包含 markdown 代码块的响应中提取 JSON"""
    text = text.strip()
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def filter_article(article: ScrapedArticle) -> FilteredArticle:
    """用 Gemini 判断单篇文章的相关性"""
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
        logger.warning("AI 过滤解析失败 [%s]: %s", article.title, e)
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
    )


def filter_articles(
    articles: list[ScrapedArticle],
    max_workers: int = 200,
    progress_cb: Callable[[str], None] | None = None,
) -> list[FilteredArticle]:
    """并发过滤所有文章"""
    total = len(articles)
    results: list[FilteredArticle] = [None] * total  # 保持顺序
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
                    "AI 过滤 [%d/%d]: %s %s",
                    current, total, status, result.title[:50],
                )
                if progress_cb and current % 5 == 0:
                    progress_cb(f"AI 过滤进度 ({current}/{total})...")
            except Exception as exc:
                logger.error("过滤任务异常: %s", exc)

    if progress_cb:
        progress_cb(f"AI 过滤完成 ({total}/{total})")

    return [r for r in results if r is not None]


def get_relevant_articles(
    filtered: list[FilteredArticle], min_confidence: float = 0.6
) -> list[FilteredArticle]:
    """筛选出相关且置信度达标的文章"""
    return [
        a for a in filtered
        if a.is_relevant and a.confidence >= min_confidence
    ]
