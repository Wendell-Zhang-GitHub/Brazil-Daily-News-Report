"""IBGE 新闻 — 使用官方 JSON API (servicodados.ibge.gov.br)"""
from __future__ import annotations

import datetime as dt
import json
import logging

from ..config import ScrapedArticle
from .base import BaseScraper, normalize_text

logger = logging.getLogger(__name__)


class IbgeScraper(BaseScraper):
    """通过 IBGE 官方 API 获取新闻，避免 agenciadenoticias 的 403 反爬"""

    def scrape(self) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []

        for api_url in self.source.list_urls:
            try:
                payload = self.client.get(api_url, verify_ssl=self.source.verify_ssl)
                data = json.loads(payload)
            except Exception as exc:
                logger.warning("IBGE API 请求失败 %s: %s", api_url, exc)
                continue

            items = data.get("items", [])
            for item in items[: self.source.max_candidates]:
                article = self._parse_item(item)
                if not article:
                    continue
                if self.start_date and self.end_date and article.published_date:
                    if not (self.start_date <= article.published_date <= self.end_date):
                        continue
                articles.append(article)

        return self._dedupe(articles)

    def _parse_item(self, item: dict) -> ScrapedArticle | None:
        title = normalize_text(item.get("titulo", ""))
        if not title:
            return None

        intro = normalize_text(item.get("introducao", ""))
        if len(intro) < 50:
            return None

        link = item.get("link", "")
        if not link:
            return None

        pub_date = self._parse_date(item.get("data_publicacao", ""))

        return ScrapedArticle(
            source_name=self.source.name,
            source_category=self.source.category,
            source_country=self.source.country,
            title=title,
            url=link,
            published_at=pub_date.isoformat() if pub_date else None,
            body=intro,
            raw_date_text=item.get("data_publicacao", ""),
            scraped_at=dt.datetime.now(dt.UTC).isoformat(),
            source_officiality=self.source.officiality,
            source_credibility=self.source.credibility,
        )

    @staticmethod
    def _parse_date(raw: str) -> dt.date | None:
        """解析 IBGE 日期格式: '16/03/2026 02:25:28'"""
        if not raw:
            return None
        try:
            return dt.datetime.strptime(raw.split()[0], "%d/%m/%Y").date()
        except (ValueError, IndexError):
            return None
