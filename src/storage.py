"""JSON 持久化"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any

from .config import DATA_DIR, DEFAULT_OUTPUT_DIR, ScrapedArticle, FilteredArticle

logger = logging.getLogger(__name__)

LOGS_DIR = DATA_DIR / "logs"


def _safe_filename(name: str) -> str:
    return re.sub(r'[^\w\u4e00-\u9fff-]', '_', name)


def save_raw_articles(articles: list[ScrapedArticle], source_name: str, run_date: str) -> Path:
    dir_path = DATA_DIR / "raw" / run_date
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{_safe_filename(source_name)}.json"
    data = [dataclasses.asdict(a) for a in articles]
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("保存 %d 篇原始文章到 %s", len(articles), file_path)
    return file_path


def load_raw_articles(source_name: str, run_date: str) -> list[ScrapedArticle] | None:
    file_path = DATA_DIR / "raw" / run_date / f"{_safe_filename(source_name)}.json"
    if not file_path.exists():
        return None
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return [ScrapedArticle(**item) for item in data]


def save_filtered_articles(articles: list[FilteredArticle], run_date: str) -> Path:
    dir_path = DATA_DIR / "filtered"
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{run_date}_filtered.json"
    data = [dataclasses.asdict(a) for a in articles]
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("保存 %d 篇过滤文章到 %s", len(articles), file_path)
    return file_path


def load_filtered_articles(run_date: str) -> list[FilteredArticle] | None:
    file_path = DATA_DIR / "filtered" / f"{run_date}_filtered.json"
    if not file_path.exists():
        return None
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return [FilteredArticle(**item) for item in data]


def save_selected_articles(articles: list[FilteredArticle], run_date: str) -> Path:
    dir_path = DATA_DIR / "selected"
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / f"{run_date}_selected.json"
    data = [dataclasses.asdict(a) for a in articles]
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("保存 %d 篇精选文章到 %s", len(articles), file_path)
    return file_path


def load_selected_articles(run_date: str) -> list[FilteredArticle] | None:
    file_path = DATA_DIR / "selected" / f"{run_date}_selected.json"
    if not file_path.exists():
        return None
    data = json.loads(file_path.read_text(encoding="utf-8"))
    return [FilteredArticle(**item) for item in data]


def save_report(content: str, start_date: str, end_date: str) -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DEFAULT_OUTPUT_DIR / f"report_{start_date}_{end_date}.md"
    file_path.write_text(content, encoding="utf-8")
    logger.info("报告已保存到 %s", file_path)
    return file_path


def save_run_log(run_date: str, log_data: dict[str, Any]) -> Path:
    """保存单次运行日志（含各阶段统计）"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = LOGS_DIR / f"{run_date}_{timestamp}.json"
    file_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("运行日志已保存到 %s", file_path)
    return file_path


def load_run_logs(limit: int = 20) -> list[dict[str, Any]]:
    """加载最近的运行日志（按时间倒序）"""
    if not LOGS_DIR.exists():
        return []
    files = sorted(LOGS_DIR.glob("*.json"), reverse=True)[:limit]
    logs = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_log_file"] = f.name
            logs.append(data)
        except Exception as exc:
            logger.warning("读取日志 %s 失败: %s", f.name, exc)
    return logs
