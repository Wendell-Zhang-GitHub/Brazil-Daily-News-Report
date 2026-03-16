"""IBGE 新闻"""
from __future__ import annotations

from .base import BaseScraper


class IbgeScraper(BaseScraper):
    """IBGE 新闻解析器"""

    def _body_selectors(self) -> list[str]:
        return [
            ".materia-conteudo",
            ".noticia-conteudo",
            "#parent-fieldname-text",
            "article",
        ]
