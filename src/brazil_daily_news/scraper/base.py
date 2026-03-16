"""BaseScraper 抽象类 + 通用工具"""
from __future__ import annotations

import abc
import datetime as dt
import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..config import ScrapedArticle, Source
from .http_client import HttpClient

logger = logging.getLogger(__name__)

BLOCKED_TITLES = {"Últimas Notícias", "Notícias", "Home", "首页", ""}

DATE_PATTERNS = [
    re.compile(r"Publicado em\s+(\d{2}/\d{2}/\d{4})"),
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(\d{2}/\d{2}/\d{4})"),
    re.compile(r"(\d{4}\.\d{2}\.\d{2})"),
    re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日)"),
]

DATE_FORMATS = ("%d/%m/%Y", "%Y-%m-%d", "%Y.%m.%d", "%Y年%m月%d日")
PT_MONTHS = {
    "jan": 1,
    "fev": 2,
    "mar": 3,
    "abr": 4,
    "mai": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "set": 9,
    "out": 10,
    "nov": 11,
    "dez": 12,
}

BODY_SELECTORS = [
    "#parent-fieldname-text",
    ".news-content",
    ".field-name-body",
    ".field-item",
    ".texto-noticia",
    ".node-content",
    ".content",
    ".content-area",
    "#content-core",
    "article",
    ".maincontent",
    ".text",
]

TITLE_SELECTORS = [
    "h1.documentFirstHeading",
    "h1",
    "title",
]


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def extract_date_from_meta(soup: BeautifulSoup) -> dt.date | None:
    """优先从 meta/time 标签提取日期"""
    # <meta property="article:published_time">
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        try:
            return dt.date.fromisoformat(meta["content"][:10])
        except ValueError:
            pass
    # <time datetime="">
    time_tag = soup.find("time", datetime=True)
    if time_tag:
        try:
            return dt.date.fromisoformat(time_tag["datetime"][:10])
        except ValueError:
            pass
    # <span class="documentPublished">
    pub_span = soup.find("span", class_="documentPublished")
    if pub_span:
        text = pub_span.get_text()
        parsed = parse_date_from_text(text)
        if parsed:
            return parsed
    return None


def parse_date_from_text(text: str, limit_chars: int = 0) -> dt.date | None:
    """从文本中正则提取日期"""
    search_text = text[:limit_chars] if limit_chars else text
    for pattern in DATE_PATTERNS:
        match = pattern.search(search_text)
        if not match:
            continue
        candidate = match.group(1)
        for fmt in DATE_FORMATS:
            try:
                return dt.datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    pt_match = re.search(r"(\d{1,2})\s+(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\s+(\d{4})", search_text, re.IGNORECASE)
    if pt_match:
        day = int(pt_match.group(1))
        month = PT_MONTHS[pt_match.group(2).lower()]
        year = int(pt_match.group(3))
        try:
            return dt.date(year, month, day)
        except ValueError:
            return None
    return None


def extract_date(soup: BeautifulSoup, html: str, body: str) -> tuple[dt.date | None, str]:
    """
    提取日期，优先级：meta/time → 文章头部2000字符正则 → 全文正则
    返回 (date, raw_date_text)
    """
    # 1. meta/time 标签
    date = extract_date_from_meta(soup)
    if date:
        return date, date.isoformat()
    # 2. 文章头部正则
    date = parse_date_from_text(html, limit_chars=2000)
    if date:
        return date, date.isoformat()
    # 3. body 正则
    date = parse_date_from_text(body)
    if date:
        return date, date.isoformat()
    return None, ""


def extract_body(soup: BeautifulSoup, selectors: list[str] | None = None) -> str:
    """多选择器回退提取正文"""
    for selector in (selectors or BODY_SELECTORS):
        node = soup.select_one(selector)
        if node:
            text = normalize_text(node.get_text(" ", strip=True))
            if text and len(text) > 50:
                return text
    return normalize_text(soup.get_text(" ", strip=True))


def extract_title(soup: BeautifulSoup) -> str:
    for attrs in (
        {"property": "og:title"},
        {"name": "twitter:title"},
    ):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            text = normalize_text(meta["content"])
            text = re.sub(r"\s*[|·-]\s*[^|·-]+$", "", text).strip()
            if text and text not in BLOCKED_TITLES:
                return text
    if soup.title:
        text = normalize_text(soup.title.get_text(" ", strip=True))
        text = re.sub(r"\s*[|·-]\s*[^|·-]+$", "", text).strip()
        if text and text not in BLOCKED_TITLES:
            return text
    for selector in TITLE_SELECTORS:
        node = soup.select_one(selector)
        if node:
            text = normalize_text(node.get_text(" ", strip=True))
            if text and text not in BLOCKED_TITLES:
                return text
    return ""


def collect_anchor_urls(
    html: str,
    base_url: str,
    entry_url_regex: str | None = None,
    extra_selectors: list[str] | None = None,
) -> list[str]:
    """从页面收集候选链接"""
    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(entry_url_regex) if entry_url_regex else None
    urls: list[str] = []

    # 先尝试特定选择器
    if extra_selectors:
        for selector in extra_selectors:
            for el in soup.select(selector):
                href = el.get("href")
                if not href:
                    a_tag = el.find("a", href=True)
                    if a_tag:
                        href = a_tag["href"]
                if href:
                    full = urljoin(base_url, href)
                    if urlparse(full).scheme not in {"http", "https"}:
                        continue
                    if pattern and not pattern.search(full):
                        continue
                    urls.append(full.split("#", 1)[0])

    # 通用 anchor 收集
    for anchor in soup.find_all("a", href=True):
        href = urljoin(base_url, anchor["href"])
        if urlparse(href).scheme not in {"http", "https"}:
            continue
        if pattern and not pattern.search(href):
            continue
        urls.append(href.split("#", 1)[0])

    # 去重保序
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


class BaseScraper(abc.ABC):
    """解析器基类"""

    def __init__(
        self,
        client: HttpClient,
        source: Source,
        start_date: dt.date | None = None,
        end_date: dt.date | None = None,
    ):
        self.client = client
        self.source = source
        self.start_date = start_date
        self.end_date = end_date

    def scrape(self) -> list[ScrapedArticle]:
        """抓取该源的所有文章，只保留日期范围内的"""
        articles: list[ScrapedArticle] = []
        candidate_urls = self._collect_urls()
        logger.info(
            "源 %s: 发现 %d 个候选链接", self.source.name, len(candidate_urls)
        )
        for url in candidate_urls[: self.source.max_candidates]:
            article = self._parse_article(url)
            if article:
                # 日期过滤：如果有日期且不在范围内，跳过
                if self.start_date and self.end_date and article.published_date:
                    if not (self.start_date <= article.published_date <= self.end_date):
                        logger.debug(
                            "跳过（日期 %s 不在范围内）: %s",
                            article.published_at, article.title[:40],
                        )
                        continue
                articles.append(article)
        return self._dedupe(articles)

    def _collect_urls(self) -> list[str]:
        """从列表页收集文章链接"""
        all_urls: list[str] = []
        for list_url in self.source.list_urls:
            try:
                html = self.client.get(list_url, verify_ssl=self.source.verify_ssl)
            except Exception as exc:
                logger.warning("抓取列表失败 %s: %s", list_url, exc)
                continue
            urls = collect_anchor_urls(
                html,
                self.source.base_url,
                self.source.entry_url_regex,
                extra_selectors=self._list_selectors(),
            )
            # 排除列表页本身
            all_urls.extend(u for u in urls if u not in self.source.list_urls)
        return all_urls

    def _list_selectors(self) -> list[str] | None:
        """子类可覆盖，提供列表页特定的链接选择器"""
        return None

    def _parse_article(self, url: str) -> ScrapedArticle | None:
        """抓取并解析单篇文章"""
        try:
            html = self.client.get(url, verify_ssl=self.source.verify_ssl)
        except Exception as exc:
            logger.warning("抓取文章失败 %s: %s", url, exc)
            return None

        soup = BeautifulSoup(html, "html.parser")
        title = extract_title(soup)
        if not title or title in BLOCKED_TITLES:
            return None

        body = extract_body(soup, self._body_selectors())
        if len(body) < 150:
            logger.debug("正文过短（%d字），跳过: %s", len(body), url)
            return None
        date, raw_date = extract_date(soup, html, body)

        return ScrapedArticle(
            source_name=self.source.name,
            source_category=self.source.category,
            source_country=self.source.country,
            title=title,
            url=url,
            published_at=date.isoformat() if date else None,
            body=body,
            raw_date_text=raw_date,
            scraped_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            source_officiality=self.source.officiality,
            source_credibility=self.source.credibility,
        )

    def _body_selectors(self) -> list[str] | None:
        """子类可覆盖，提供正文提取选择器"""
        return None

    @staticmethod
    def _dedupe(articles: list[ScrapedArticle]) -> list[ScrapedArticle]:
        seen: set[str] = set()
        result: list[ScrapedArticle] = []
        for a in articles:
            if a.url not in seen:
                seen.add(a.url)
                result.append(a)
        return result
