"""人民网、新华网"""
from __future__ import annotations

from .base import BaseScraper


class ChineseMediaScraper(BaseScraper):
    """人民网国际频道 / 新华网"""

    def _body_selectors(self) -> list[str]:
        return [
            ".rm_txt_con",       # 人民网
            "#p-detail",         # 新华网
            ".article",
            ".detail_con",
            "#content",
            "article",
        ]
