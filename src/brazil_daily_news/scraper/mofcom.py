"""商务部驻巴西处 + 商务部本部"""
from __future__ import annotations

import datetime as dt
import logging
import time

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ..config import ScrapedArticle
from .base import BaseScraper, normalize_text, parse_date_from_text, extract_body, extract_title, extract_date

logger = logging.getLogger(__name__)


class MofcomHomeScraper(BaseScraper):
    """商务部驻巴西经商处首页解析器 — 不再硬编码"巴西"过滤"""

    def scrape(self) -> list[ScrapedArticle]:
        articles: list[ScrapedArticle] = []
        deadline = time.time() + self.SOURCE_TIMEOUT
        for list_url in self.source.list_urls:
            try:
                html = self.client.get(list_url, verify_ssl=self.source.verify_ssl)
            except Exception as exc:
                logger.warning("抓取列表失败 %s: %s", list_url, exc)
                continue

            soup = BeautifulSoup(html, "html.parser")
            seen: set[str] = set()

            for anchor in soup.find_all("a", href=True):
                if time.time() > deadline:
                    logger.warning(
                        "源 %s: 超时（%ds），已抓取 %d 篇，跳过剩余",
                        self.source.name, self.SOURCE_TIMEOUT, len(articles),
                    )
                    break
                href = urljoin(self.source.base_url, anchor["href"])
                text = normalize_text(anchor.get_text(" ", strip=True))
                if not text or href in seen:
                    continue
                seen.add(href)

                line = normalize_text(anchor.parent.get_text(" ", strip=True))
                published_at = parse_date_from_text(line) or parse_date_from_text(text)

                # 尝试抓取完整正文
                body = line
                try:
                    article_html = self.client.get(href, verify_ssl=self.source.verify_ssl)
                    article_soup = BeautifulSoup(article_html, "html.parser")
                    full_body = extract_body(article_soup)
                    if full_body and len(full_body) > len(line):
                        body = full_body
                    full_title = extract_title(article_soup)
                    if full_title:
                        text = full_title
                    date, _ = extract_date(article_soup, article_html, body)
                    if date:
                        published_at = date
                except Exception:
                    pass

                # 日期过滤
                if self.start_date and self.end_date and published_at:
                    if not (self.start_date <= published_at <= self.end_date):
                        continue

                articles.append(ScrapedArticle(
                    source_name=self.source.name,
                    source_category=self.source.category,
                    source_country=self.source.country,
                    title=text,
                    url=href,
                    published_at=published_at.isoformat() if published_at else None,
                    body=body,
                    raw_date_text=published_at.isoformat() if published_at else "",
                    scraped_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                ))

        return self._dedupe(articles)[: self.source.max_candidates]


class MofcomScraper(BaseScraper):
    """商务部本部通用解析器"""
    pass
