"""港澳事务办公室"""
from __future__ import annotations

from .base import BaseScraper


class HmoScraper(BaseScraper):
    """港澳事务办公室"""

    def _body_selectors(self) -> list[str]:
        return [
            ".pages_content",
            ".TRS_Editor",
            ".article-content",
            "article",
        ]
