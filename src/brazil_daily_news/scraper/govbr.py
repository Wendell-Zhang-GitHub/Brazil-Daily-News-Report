"""gov.br 系列解析器（MDIC, Siscomex, Fazenda, Planalto, Camex）— 最关键"""
from __future__ import annotations

from .base import BaseScraper


class GovBrScraper(BaseScraper):
    """gov.br 网站专用解析器，多选择器策略"""

    def _list_selectors(self) -> list[str]:
        return [
            ".tileItem a",
            "article a",
            ".noticias-lista a",
            ".listagem-noticias a",
            ".items-list a",
            ".tile-item a",
        ]

    def _body_selectors(self) -> list[str]:
        return [
            "#parent-fieldname-text",
            ".content-area",
            "#content-core",
            ".materia-conteudo",
            "article",
            ".text",
        ]
