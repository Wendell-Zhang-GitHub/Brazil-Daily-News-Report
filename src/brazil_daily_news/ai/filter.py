"""Claude Haiku 相关性过滤"""
from __future__ import annotations

import json
import logging
import re

from ..config import ScrapedArticle, FilteredArticle
from .client import call_haiku
from .prompts import FILTER_SYSTEM, FILTER_USER_TEMPLATE

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> dict:
    """从可能包含 markdown 代码块的响应中提取 JSON"""
    text = text.strip()
    # 去掉 ```json ... ``` 包裹
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    return json.loads(text)


def filter_article(article: ScrapedArticle) -> FilteredArticle:
    """用 Haiku 判断单篇文章的相关性"""
    body_preview = article.body[:500] if article.body else ""

    user_content = FILTER_USER_TEMPLATE.format(
        source_name=article.source_name,
        title=article.title,
        body_preview=body_preview,
    )

    try:
        response_text = call_haiku(FILTER_SYSTEM, user_content)
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


def filter_articles(articles: list[ScrapedArticle]) -> list[FilteredArticle]:
    """过滤所有文章，返回全部结果（含不相关的）"""
    results: list[FilteredArticle] = []
    total = len(articles)
    for i, article in enumerate(articles, 1):
        logger.info("AI 过滤 [%d/%d]: %s", i, total, article.title[:60])
        result = filter_article(article)
        results.append(result)
        status = "✓ 相关" if result.is_relevant else "✗ 不相关"
        logger.info("  %s (%.1f) — %s", status, result.confidence, result.reason[:80])
    return results


def get_relevant_articles(
    filtered: list[FilteredArticle], min_confidence: float = 0.6
) -> list[FilteredArticle]:
    """筛选出相关且置信度达标的文章"""
    return [
        a for a in filtered
        if a.is_relevant and a.confidence >= min_confidence
    ]
