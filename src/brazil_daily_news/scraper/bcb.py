"""BCB Focus PDF 探测"""
from __future__ import annotations

import datetime as dt
import logging

from ..config import ScrapedArticle
from .base import BaseScraper

logger = logging.getLogger(__name__)


class BcbFocusScraper(BaseScraper):
    """BCB Focus 报告 — HEAD 请求探测 PDF"""

    def scrape(self) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []
        today = dt.date.today()

        # 只探测日期范围内的 PDF
        search_start = self.start_date or (today - dt.timedelta(days=self.source.max_candidates))
        search_end = self.end_date or today
        days_range = (search_end - search_start).days + 1

        for days_back in range(days_range):
            candidate = search_end - dt.timedelta(days=days_back)
            url = f"{self.source.base_url}/content/focus/focus/R{candidate.strftime('%Y%m%d')}.pdf"
            try:
                response = self.client.head(url, verify_ssl=self.source.verify_ssl)
            except Exception as exc:
                logger.warning("检查 BCB Focus 失败 %s: %s", url, exc)
                continue

            if response.status_code >= 400:
                continue

            title = f"BCB Focus Relatório de Mercado {candidate.isoformat()}"
            body = (
                f"BCB Focus Relatório de Mercado {candidate.isoformat()} "
                "juros inflação câmbio PIB expectativas mercado"
            )
            articles.append(ScrapedArticle(
                source_name=self.source.name,
                source_category=self.source.category,
                source_country=self.source.country,
                title=title,
                url=url,
                published_at=candidate.isoformat(),
                body=body,
                raw_date_text=candidate.isoformat(),
                scraped_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            ))

        return articles
