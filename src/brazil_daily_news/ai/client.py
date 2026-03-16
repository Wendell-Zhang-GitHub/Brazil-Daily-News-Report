"""AI API 封装：Gemini 原生 API（过滤）+ OpenAI 兼容 API（报告）"""
from __future__ import annotations

import logging
import os
import threading
import time

import requests as http_requests
from openai import OpenAI

logger = logging.getLogger(__name__)

_local = threading.local()


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"必需的环境变量 {key} 未设置")
    return val


# ── Gemini 原生 API（用于过滤）──────────────────────────────
GEMINI_API_KEY = _require_env("GEMINI_API_KEY")
GEMINI_MODEL = _require_env("GEMINI_MODEL")
_FILTER_CONCURRENCY = int(os.environ.get("GEMINI_CONCURRENCY", "200"))
_filter_semaphore = threading.Semaphore(_FILTER_CONCURRENCY)

GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


def call_filter(system: str, user_content: str, max_tokens: int = 1024) -> str:
    """调用 Gemini API 进行过滤，信号量控制并发 + 重试"""
    with _filter_semaphore:
        for attempt in range(5):
            try:
                resp = http_requests.post(
                    GEMINI_API_URL,
                    params={"key": GEMINI_API_KEY},
                    json={
                        "contents": [
                            {"role": "user", "parts": [{"text": user_content}]},
                        ],
                        "systemInstruction": {"parts": [{"text": system}]},
                        "generationConfig": {
                            "temperature": 0.3,
                            "maxOutputTokens": max_tokens,
                        },
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                err_str = str(e).lower()
                if "429" in str(e) or "rate" in err_str or "resource" in err_str:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "Gemini 限速，等待 %ds 后重试 (attempt %d/5)",
                        wait, attempt + 1,
                    )
                    time.sleep(wait)
                else:
                    logger.error("Gemini 调用失败: %s", e)
                    if attempt == 4:
                        raise
                    time.sleep(1)
        raise RuntimeError("Gemini 调用失败，重试已耗尽")


# ── OpenAI 兼容 API（用于报告生成）─────────────────────────
SONNET_MODEL = _require_env("AI_SONNET_MODEL")
_report_semaphore = threading.Semaphore(3)


def configure(api_key: str | None = None, base_url: str | None = None) -> None:
    """为当前线程设置 API 凭据（Web 模式下由用户提供）"""
    _local.api_key = api_key
    _local.base_url = base_url
    _local.client = None


def _get_config() -> tuple[str, str]:
    api_key = getattr(_local, "api_key", None) or os.environ.get("AI_API_KEY")
    base_url = getattr(_local, "base_url", None) or os.environ.get("AI_BASE_URL")
    if not api_key:
        raise RuntimeError("AI_API_KEY 未设置：请设置环境变量")
    if not base_url:
        raise RuntimeError("AI_BASE_URL 未设置：请设置环境变量")
    return api_key, base_url


def get_client() -> OpenAI:
    client = getattr(_local, "client", None)
    if client is None:
        api_key, base_url = _get_config()
        client = OpenAI(api_key=api_key, base_url=base_url)
        _local.client = client
    return client


def call_sonnet(system: str, user_content: str, max_tokens: int = 8000) -> str:
    """调用 Claude Sonnet（OpenAI 兼容格式）"""
    with _report_semaphore:
        client = get_client()
        for attempt in range(5):
            try:
                response = client.chat.completions.create(
                    model=SONNET_MODEL,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.5,
                )
                return response.choices[0].message.content
            except Exception as e:
                if "rate" in str(e).lower() or "429" in str(e):
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "Sonnet 限速，等待 %ds 后重试 (attempt %d/5)",
                        wait, attempt + 1,
                    )
                    time.sleep(wait)
                else:
                    logger.error("Sonnet 调用失败: %s", e)
                    if attempt == 4:
                        raise
                    time.sleep(1)
        raise RuntimeError("Sonnet 调用失败，重试已耗尽")
