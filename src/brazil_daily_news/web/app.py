"""FastAPI Web 应用"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..config import DEFAULT_OUTPUT_DIR
from .tasks import submit_task, get_task

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


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    task_id = submit_task(
        req.start_date, req.end_date, req.force,
        api_key=req.api_key, base_url=req.base_url,
    )
    return {"task_id": task_id}


@app.get("/api/tasks/{task_id}")
async def task_status(task_id: str):
    task = get_task(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task.to_dict()


@app.get("/api/reports")
async def list_reports():
    if not DEFAULT_OUTPUT_DIR.exists():
        return []
    files = sorted(DEFAULT_OUTPUT_DIR.glob("weekly_report_*.md"), reverse=True)
    return [{"name": f.name, "size": f.stat().st_size} for f in files]


@app.get("/api/reports/{name}")
async def get_report(name: str):
    # 防止路径遍历
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "无效的文件名")
    file_path = DEFAULT_OUTPUT_DIR / name
    if not file_path.exists() or not file_path.suffix == ".md":
        raise HTTPException(404, "报告不存在")
    return JSONResponse({"name": name, "content": file_path.read_text(encoding="utf-8")})


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
