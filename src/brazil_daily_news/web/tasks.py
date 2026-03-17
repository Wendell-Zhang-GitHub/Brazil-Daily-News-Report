"""后台任务管理"""
from __future__ import annotations

import logging
import threading
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
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    task_id: str
    status: TaskStatus = TaskStatus.PENDING
    progress: str = ""
    result: str | None = None
    error: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)

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
    max_articles: int = 6,
) -> None:
    task = _tasks[task_id]
    task.status = TaskStatus.RUNNING

    # 在当前线程设置 API 凭据
    from ..ai.client import configure
    configure(api_key=api_key, base_url=base_url)

    def on_progress(msg: str) -> None:
        if task.cancel_event.is_set():
            raise InterruptedError("任务已被用户取消")
        task.progress = msg

    try:
        report = pipeline_run(
            start_date=start_date,
            end_date=end_date,
            force=force,
            progress_callback=on_progress,
            max_articles=max_articles,
        )
        if task.cancel_event.is_set():
            task.status = TaskStatus.CANCELLED
            task.progress = "任务已取消"
        else:
            task.result = report or ""
            task.status = TaskStatus.COMPLETED
    except InterruptedError:
        task.status = TaskStatus.CANCELLED
        task.progress = "任务已取消"
        logger.info("任务 %s 已被取消", task_id)
    except Exception as exc:
        if task.cancel_event.is_set():
            task.status = TaskStatus.CANCELLED
            task.progress = "任务已取消"
        else:
            logger.exception("Pipeline 执行失败")
            task.error = str(exc)
            task.status = TaskStatus.FAILED


def submit_task(
    start_date: str,
    end_date: str,
    force: bool = False,
    api_key: str | None = None,
    base_url: str | None = None,
    max_articles: int = 6,
) -> str:
    task_id = uuid.uuid4().hex[:12]
    task = TaskInfo(task_id=task_id)
    _tasks[task_id] = task
    _executor.submit(_run_pipeline, task_id, start_date, end_date, force, api_key, base_url, max_articles)
    return task_id


def cancel_task(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if not task:
        return False
    task.cancel_event.set()
    task.status = TaskStatus.CANCELLED
    task.progress = "正在取消..."
    return True


def get_task(task_id: str) -> TaskInfo | None:
    return _tasks.get(task_id)
