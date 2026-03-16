"""配置加载 + 数据模型"""
from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "sources.yaml"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data"


@dataclasses.dataclass
class Source:
    name: str
    country: str
    category: str
    base_url: str
    list_urls: list[str]
    parser: str
    enabled: bool
    priority: int
    verify_ssl: bool = True
    max_candidates: int = 20
    entry_url_regex: str | None = None


@dataclasses.dataclass
class ScrapedArticle:
    source_name: str
    source_category: str
    source_country: str
    title: str
    url: str
    published_at: str | None  # ISO format string for JSON serialization
    body: str
    raw_date_text: str
    scraped_at: str  # ISO format timestamp

    @property
    def published_date(self) -> dt.date | None:
        if self.published_at:
            try:
                return dt.date.fromisoformat(self.published_at)
            except ValueError:
                return None
        return None


@dataclasses.dataclass
class FilteredArticle:
    source_name: str
    source_category: str
    source_country: str
    title: str
    url: str
    published_at: str | None
    body: str
    is_relevant: bool
    confidence: float
    category: str
    reason: str

    @property
    def published_date(self) -> dt.date | None:
        if self.published_at:
            try:
                return dt.date.fromisoformat(self.published_at)
            except ValueError:
                return None
        return None


def load_config(path: Path | None = None) -> tuple[dict[str, Any], list[Source]]:
    config_path = path or DEFAULT_CONFIG_PATH
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    report_config = config.get("report", {})
    sources = [
        Source(**entry)
        for entry in config.get("sources", [])
        if entry.get("enabled", True)
    ]
    return report_config, sources
