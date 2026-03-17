"""AI API 封装：Gemini 原生 API（过滤）+ OpenAI 兼容 API（报告）"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable

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
FILTER_MAX_CONCURRENCY = int(os.environ.get("GEMINI_CONCURRENCY", "200"))

GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


def call_filter(system: str, user_content: str, max_tokens: int = 1024) -> str:
    """调用 Gemini API 进行过滤 + 重试"""
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


# ── Gemini 深度筛选（用于二次过滤）─────────────────────────
GEMINI_DEEP_MODEL = _require_env("GEMINI_DEEP_MODEL")

GEMINI_DEEP_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_DEEP_MODEL}:generateContent"
)


def call_deep_filter(system: str, user_content: str, max_tokens: int = 4096) -> str:
    """调用 Gemini Flash 进行深度筛选（单次调用，不需高并发）"""
    for attempt in range(5):
        try:
            resp = http_requests.post(
                GEMINI_DEEP_API_URL,
                params={"key": GEMINI_API_KEY},
                json={
                    "contents": [
                        {"role": "user", "parts": [{"text": user_content}]},
                    ],
                    "systemInstruction": {"parts": [{"text": system}]},
                    "generationConfig": {
                        "temperature": 0.2,
                        "maxOutputTokens": max_tokens,
                    },
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            err_str = str(e).lower()
            if "429" in str(e) or "rate" in err_str or "resource" in err_str:
                wait = 2 ** (attempt + 1)
                logger.warning(
                    "Gemini Deep 限速，等待 %ds 后重试 (attempt %d/5)",
                    wait, attempt + 1,
                )
                time.sleep(wait)
            else:
                logger.error("Gemini Deep 调用失败: %s", e)
                if attempt == 4:
                    raise
                time.sleep(1)
    raise RuntimeError("Gemini Deep 调用失败，重试已耗尽")


# ── OpenAI 兼容 API（用于报告生成）─────────────────────────
SONNET_MODEL = _require_env("AI_SONNET_MODEL")
REPORT_FALLBACK_MODELS = [
    os.environ.get("AI_FALLBACK_MODEL_1", "claude-opus-4-6"),
    os.environ.get("AI_FALLBACK_MODEL_2", "gpt-5.4"),
]
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


def _call_model(
    client: OpenAI,
    model: str,
    system: str,
    user_content: str,
    max_tokens: int,
    max_retries: int = 5,
) -> str:
    """对单个模型做重试，失败则抛异常"""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
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
                    "%s 限速，等待 %ds 后重试 (attempt %d/%d)",
                    model, wait, attempt + 1, max_retries,
                )
                time.sleep(wait)
            else:
                logger.error("%s 调用失败: %s", model, e)
                if attempt == max_retries - 1:
                    raise
                time.sleep(1)
    raise RuntimeError(f"{model} 调用失败，重试已耗尽")


def call_report(
    system: str,
    user_content: str,
    max_tokens: int = 16000,
    on_model_try: Callable[[str], None] | None = None,
) -> tuple[str, str]:
    """调用报告生成模型，带 fallback 链。返回 (content, model_used)"""
    models = [SONNET_MODEL] + REPORT_FALLBACK_MODELS
    with _report_semaphore:
        client = get_client()
        for i, model in enumerate(models):
            if on_model_try:
                on_model_try(model)
            try:
                content = _call_model(client, model, system, user_content, max_tokens)
                if i > 0:
                    logger.info("使用 fallback 模型 %s 生成报告成功", model)
                return content, model
            except Exception:
                if i < len(models) - 1:
                    logger.warning(
                        "模型 %s 失败，切换到 fallback: %s", model, models[i + 1],
                    )
                else:
                    raise
    raise RuntimeError("所有报告模型均失败")
