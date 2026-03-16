"""后台任务管理"""
from __future__ import annotations

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ..pipeline import run as pipeline_run

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
_tasks: dict[str, TaskInfo] = {}


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = ""
    result: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
        }


def _run_pipeline(
    task_id: str,
    start_date: str,
    end_date: str,
    force: bool,
    api_key: str | None,
    base_url: str | None,
) -> None:
    task = _tasks[task_id]
    task.status = TaskStatus.RUNNING

    # 在当前线程设置 API 凭据
    from ..ai.client import configure
    configure(api_key=api_key, base_url=base_url)

    def on_progress(msg: str) -> None:
        task.progress = msg

    try:
        report = pipeline_run(
            start_date=start_date,
            end_date=end_date,
            force_scrape=force,
            progress_callback=on_progress,
        )
        task.result = report or ""
        task.status = TaskStatus.COMPLETED
    except Exception as exc:
        logger.exception("Pipeline 执行失败")
        task.error = str(exc)
        task.status = TaskStatus.FAILED


def submit_task(
    start_date: str,
    end_date: str,
    force: bool = False,
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    task_id = uuid.uuid4().hex[:12]
    task = TaskInfo(task_id=task_id)
    _tasks[task_id] = task
    _executor.submit(_run_pipeline, task_id, start_date, end_date, force, api_key, base_url)
    return task_id


def get_task(task_id: str) -> TaskInfo | None:
    return _tasks.get(task_id)
