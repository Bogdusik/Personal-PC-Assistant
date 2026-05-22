from __future__ import annotations
import json
import logging
import os
import time
from typing import Any

import requests

from .normalizer import _has_too_much_cjk, _extract_json

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout = 35
        self.retries = 2
        self.retry_backoff = 0.8

    @property
    def generate_url(self) -> str:
        return f"{self.base_url}/api/generate"

    def ask(
        self,
        user_text: str,
        model: str,
        system_prompt: str,
    ) -> dict[str, Any] | None:
        payload = {
            "model": model,
            "prompt": f"{system_prompt}\nФраза пользователя: {user_text}\nJSON:",
            "stream": True,
            "temperature": 0.0,
            "format": "json",
        }
        for attempt in range(self.retries + 1):
            try:
                response = requests.post(
                    self.generate_url,
                    json=payload,
                    timeout=self.timeout,
                    stream=True,
                )
                response.raise_for_status()
                buf = ""
                for line in response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        buf += data.get("response", "")
                        if data.get("done"):
                            break
                    except (json.JSONDecodeError, ValueError):
                        continue

                if _has_too_much_cjk(buf):
                    logger.warning("Ollama ответил CJK-символами, повтор запроса")
                    continue

                return _extract_json(buf)

            except requests.ConnectionError:
                logger.warning("Ollama недоступен (попытка %d/%d)", attempt + 1, self.retries + 1)
            except requests.Timeout:
                logger.warning("Ollama таймаут (попытка %d/%d)", attempt + 1, self.retries + 1)
            except requests.HTTPError as exc:
                logger.error("Ollama HTTP ошибка: %s", exc)
                return None

            if attempt < self.retries:
                time.sleep((1 + attempt) * self.retry_backoff)

        return None
