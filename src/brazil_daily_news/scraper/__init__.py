"""解析器注册表"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseScraper

# parser名 → 类 的懒加载映射
_REGISTRY: dict[str, type[BaseScraper]] = {}


def _ensure_registered() -> None:
    if _REGISTRY:
        return
    from .mofcom import MofcomHomeScraper, MofcomScraper
    from .govbr import GovBrScraper
    from .gov_cn import GovCnScraper, CustomsScraper
    from .chinese_media import ChineseMediaScraper
    from .hmo import HmoScraper
    from .ibge import IbgeScraper
    from .bcb import BcbFocusScraper
    from .rss import RssFeedScraper
    from .json_list import JsonListScraper

    _REGISTRY.update({
        "mofcom_home": MofcomHomeScraper,
        "generic_anchor": GovCnScraper,  # 通用解析器
        "govbr_news": GovBrScraper,
        "govbr": GovBrScraper,
        "gov_cn": GovCnScraper,
        "customs": CustomsScraper,
        "chinese_media": ChineseMediaScraper,
        "hmo": HmoScraper,
        "ibge": IbgeScraper,
        "bcb_focus": BcbFocusScraper,
        "rss_feed": RssFeedScraper,
        "json_list": JsonListScraper,
    })


def get_scraper(parser_name: str) -> type[BaseScraper]:
    _ensure_registered()
    if parser_name not in _REGISTRY:
        # 回退到通用解析器
        from .gov_cn import GovCnScraper
        return GovCnScraper
    return _REGISTRY[parser_name]
