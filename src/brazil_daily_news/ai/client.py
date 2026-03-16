"""OpenAI 兼容 API 封装（支持线程级动态配置 + 并发限速）"""
from __future__ import annotations

import logging
import os
import threading
import time

from openai import OpenAI

logger = logging.getLogger(__name__)

_local = threading.local()
# 信号量：限制同时并发的 API 调用数，避免触发 429
_api_semaphore = threading.Semaphore(20)

HAIKU_MODEL = os.environ.get("AI_HAIKU_MODEL", "claude-haiku-4-5-20251001")
SONNET_MODEL = os.environ.get("AI_SONNET_MODEL", "claude-sonnet-4-6")


def configure(api_key: str | None = None, base_url: str | None = None) -> None:
    """为当前线程设置 API 凭据（Web 模式下由用户提供）"""
    _local.api_key = api_key
    _local.base_url = base_url
    _local.client = None


def _get_config() -> tuple[str, str]:
    api_key = getattr(_local, "api_key", None) or os.environ.get("AI_API_KEY")
    base_url = getattr(_local, "base_url", None) or os.environ.get("AI_BASE_URL")
    if not api_key:
        raise RuntimeError("AI_API_KEY 未设置：请在前端填写或设置环境变量")
    if not base_url:
        raise RuntimeError("AI_BASE_URL 未设置：请在前端填写或设置环境变量")
    return api_key, base_url


def get_client() -> OpenAI:
    client = getattr(_local, "client", None)
    if client is None:
        api_key, base_url = _get_config()
        client = OpenAI(api_key=api_key, base_url=base_url)
        _local.client = client
    return client


def call_haiku(system: str, user_content: str, max_tokens: int = 1024) -> str:
    """调用 Claude Haiku，信号量控制并发 + 重试"""
    with _api_semaphore:
        client = get_client()
        for attempt in range(5):
            try:
                response = client.chat.completions.create(
                    model=HAIKU_MODEL,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.3,
                )
                return response.choices[0].message.content
            except Exception as e:
                if "rate" in str(e).lower() or "429" in str(e):
                    wait = 2 ** (attempt + 1)
                    logger.warning("Haiku 限速，等待 %ds 后重试 (attempt %d/5)", wait, attempt + 1)
                    time.sleep(wait)
                else:
                    logger.error("Haiku 调用失败: %s", e)
                    if attempt == 4:
                        raise
                    time.sleep(1)
        raise RuntimeError("Haiku 调用失败，重试已耗尽")


def call_sonnet(system: str, user_content: str, max_tokens: int = 8000) -> str:
    """调用 Claude Sonnet"""
    with _api_semaphore:
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
                    logger.warning("Sonnet 限速，等待 %ds 后重试 (attempt %d/5)", wait, attempt + 1)
                    time.sleep(wait)
                else:
                    logger.error("Sonnet 调用失败: %s", e)
                    if attempt == 4:
                        raise
                    time.sleep(1)
        raise RuntimeError("Sonnet 调用失败，重试已耗尽")
