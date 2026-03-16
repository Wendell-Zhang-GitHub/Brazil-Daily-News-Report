"""Claude Sonnet 报告生成"""
from __future__ import annotations

import logging

from ..config import FilteredArticle
from .client import call_sonnet
from .prompts import REPORT_SYSTEM, REPORT_USER_TEMPLATE

logger = logging.getLogger(__name__)


def _format_articles_for_prompt(articles: list[FilteredArticle]) -> str:
    """将文章格式化为 prompt 输入"""
    parts: list[str] = []
    for i, a in enumerate(articles, 1):
        body_preview = a.body[:2000] if a.body else "(无正文)"
        parts.append(
            f"--- 文章 {i} ---\n"
            f"来源：{a.source_name}（{a.source_category}）\n"
            f"标题：{a.title}\n"
            f"日期：{a.published_at or '未知'}\n"
            f"AI分类：{a.category}\n"
            f"URL：{a.url}\n"
            f"正文：\n{body_preview}\n"
        )
    return "\n".join(parts)


def generate_report(
    articles: list[FilteredArticle],
    start_date: str,
    end_date: str,
) -> str:
    """用 Sonnet 生成完整周报"""
    logger.info("开始生成报告，输入 %d 篇文章", len(articles))

    articles_text = _format_articles_for_prompt(articles)

    system = REPORT_SYSTEM.format(start_date=start_date, end_date=end_date)
    user_content = REPORT_USER_TEMPLATE.format(
        start_date=start_date,
        end_date=end_date,
        article_count=len(articles),
        articles_text=articles_text,
    )

    report = call_sonnet(system, user_content)
    logger.info("报告生成完成，长度 %d 字符", len(report))
    return report
