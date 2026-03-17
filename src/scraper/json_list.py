"""JSON 列表型新闻源解析器"""
from __future__ import annotations

import json
from urllib.parse import urljoin

from .base import BaseScraper


class JsonListScraper(BaseScraper):
    """适配返回 JSON 列表的站点，再复用通用文章解析逻辑"""

    def _collect_urls(self) -> list[str]:
        urls: list[str] = []
        for list_url in self.source.list_urls:
            try:
                payload = self.client.get(list_url, verify_ssl=self.source.verify_ssl)
                data = json.loads(payload)
            except Exception:
                continue

            for item in data.get("noticias", []):
                raw_url = item.get("url")
                if not raw_url:
                    continue
                full_url = urljoin(self.source.base_url, raw_url)
                if self.source.entry_url_regex:
                    import re

                    if not re.search(self.source.entry_url_regex, full_url):
                        continue
                urls.append(full_url)

        seen: set[str] = set()
        deduped: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                deduped.append(url)
        return deduped
