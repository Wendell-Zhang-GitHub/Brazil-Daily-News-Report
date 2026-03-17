"""FastAPI Web 应用"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .tasks import submit_task, get_task, cancel_task

logger = logging.getLogger(__name__)

app = FastAPI(title="巴西经贸信息周报")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class GenerateRequest(BaseModel):
    start_date: str
    end_date: str
    force: bool = False
    api_key: str | None = None
    base_url: str | None = None
    max_articles: int = 6


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    task_id = submit_task(
        req.start_date, req.end_date, req.force,
        api_key=req.api_key, base_url=req.base_url,
        max_articles=req.max_articles,
    )
    return {"task_id": task_id}


@app.get("/api/tasks/{task_id}")
async def task_status(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task.to_dict()


@app.post("/api/tasks/{task_id}/cancel")
async def cancel(task_id: str):
    ok = cancel_task(task_id)
    if not ok:
        raise HTTPException(404, "任务不存在")
    return {"status": "cancelled"}


@app.get("/health")
async def health():
    return {"status": "ok"}


def _keep_alive_loop():
    """后台线程：每 10 分钟 ping 自身和 Sonnet API 代理，防止 Render 冷启动"""
    urls = []

    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url:
        urls.append(f"{render_url}/health")

    # Sonnet API 代理也在 Render 上，需要保活
    ai_base_url = os.environ.get("AI_BASE_URL", "")
    if "onrender.com" in ai_base_url:
        # 去掉末尾 /v1 等路径，ping 根路径
        proxy_base = ai_base_url.rstrip("/").removesuffix("/v1")
        urls.append(proxy_base)

    if not urls:
        logger.info("无需 keep-alive（非 Render 环境）")
        return

    logger.info("Keep-alive 启动，每 10 分钟 ping: %s", urls)
    while True:
        time.sleep(600)
        for url in urls:
            try:
                resp = requests.get(url, timeout=10)
                logger.debug("Keep-alive ping %s: %s", url, resp.status_code)
            except Exception as exc:
                logger.warning("Keep-alive ping %s 失败: %s", url, exc)


@app.on_event("startup")
async def startup_event():
    t = threading.Thread(target=_keep_alive_loop, daemon=True)
    t.start()


def main():
    import uvicorn
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
