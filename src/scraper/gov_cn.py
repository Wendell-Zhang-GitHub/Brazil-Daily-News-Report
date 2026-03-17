"""中国政府网 + 海关总署"""
from __future__ import annotations

from .base import BaseScraper


class GovCnScraper(BaseScraper):
    """中国政府网通用解析器，也作为 generic_anchor 的实现"""

    def _body_selectors(self) -> list[str]:
        return [
            ".pages_content",
            ".article",
            "#UCAP-CONTENT",
            ".news-content",
            "#parent-fieldname-text",
            "article",
            ".maincontent",
        ]


class CustomsScraper(BaseScraper):
    """海关总署"""

    def _body_selectors(self) -> list[str]:
        return [
            ".easysite-news-text",
            ".TRS_Editor",
            ".article-content",
            "article",
        ]
