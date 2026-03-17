"""RSS/Atom 订阅源解析器"""
from __future__ import annotations

import datetime as dt
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from ..config import ScrapedArticle
from .base import BaseScraper, normalize_text


class RssFeedScraper(BaseScraper):
    """直接消费 RSS/Atom feed，适合稳定的媒体和机构订阅流"""

    def scrape(self) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []

        for feed_url in self.source.list_urls:
            try:
                xml = self.client.get(feed_url, verify_ssl=self.source.verify_ssl)
            except Exception:
                continue

            soup = BeautifulSoup(xml, "xml")
            items = soup.find_all(["item", "entry"])
            for item in items[: self.source.max_candidates]:
                article = self._parse_feed_item(item)
                if not article:
                    continue
                if self.start_date and self.end_date and article.published_date:
                    if not (self.start_date <= article.published_date <= self.end_date):
                        continue
                articles.append(article)

        return self._dedupe(articles)

    def _parse_feed_item(self, item: BeautifulSoup) -> ScrapedArticle | None:
        title = normalize_text(item.title.get_text(" ", strip=True)) if item.title else ""
        if not title:
            return None

        url = ""
        if item.link:
            url = item.link.get("href") or item.link.get_text(" ", strip=True)
        if not url:
            return None

        body_html = ""
        for tag_name in ("content:encoded", "encoded", "description", "summary", "content"):
            node = item.find(tag_name)
            if node and node.get_text(" ", strip=True):
                body_html = node.get_text(" ", strip=True)
                break

        body = normalize_text(BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True))
        if len(body) < 80:
            return None

        published = self._parse_pub_date(item)
        published_at = published.isoformat() if published else None

        return ScrapedArticle(
            source_name=self.source.name,
            source_category=self.source.category,
            source_country=self.source.country,
            title=title,
            url=url,
            published_at=published_at,
            body=body,
            raw_date_text=published_at or "",
            scraped_at=dt.datetime.now(dt.UTC).isoformat(),
            source_officiality=self.source.officiality,
            source_credibility=self.source.credibility,
        )

    def _parse_pub_date(self, item: BeautifulSoup) -> dt.date | None:
        for tag_name in ("pubDate", "published", "updated"):
            node = item.find(tag_name)
            if not node or not node.get_text(strip=True):
                continue
            raw = node.get_text(strip=True)
            try:
                return parsedate_to_datetime(raw).date()
            except (TypeError, ValueError, IndexError):
                pass
            try:
                return dt.date.fromisoformat(raw[:10])
            except ValueError:
                continue
        return None
