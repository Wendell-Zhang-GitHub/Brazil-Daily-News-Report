"""带重试、限速的 HTTP 客户端"""
from __future__ import annotations

import logging
import time

import urllib3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

USER_AGENT = "BrazilDailyNewsBot/0.2"
DEFAULT_TIMEOUT = 20
MIN_REQUEST_INTERVAL = 1.5


class HttpClient:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self._last_request_time = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,zh-CN;q=0.8,zh;q=0.7,en;q=0.6",
        })
        retry = Retry(
            total=3,
            backoff_factor=1.0,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def get(self, url: str, verify_ssl: bool = True) -> str:
        self._rate_limit()
        logger.debug("GET %s", url)
        response = self.session.get(url, timeout=self.timeout, verify=verify_ssl)
        response.raise_for_status()
        # 处理编码
        if response.encoding and response.encoding.lower() in ("iso-8859-1",) and response.apparent_encoding:
            response.encoding = response.apparent_encoding
        return response.text

    def head(self, url: str, verify_ssl: bool = True) -> requests.Response:
        self._rate_limit()
        return self.session.head(
            url, timeout=self.timeout, verify=verify_ssl, allow_redirects=True
        )
