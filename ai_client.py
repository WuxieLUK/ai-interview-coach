# -*- coding: utf-8 -*-
"""OpenAI 兼容的大模型客户端（默认 DeepSeek，可换任意兼容服务）。

带指数退避重试、可配置超时与 JSON 输出模式；失败时抛出 AIClientError，
由上层回退到离线规则评分。
"""
import json
import os
import time
import urllib.error
import urllib.request


class AIClientError(Exception):
    pass


class AIClient:
    def __init__(self):
        self.api_key = (
            os.environ.get("AI_API_KEY")
            or os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )
        self.base_url = os.environ.get("AI_BASE_URL") or "https://api.deepseek.com"
        self.model = os.environ.get("AI_MODEL") or "deepseek-chat"
        self.timeout = self._env_int("AI_TIMEOUT", 60)
        self.max_retries = self._env_int("AI_MAX_RETRIES", 2)

    @staticmethod
    def _env_int(name, default):
        try:
            return int(os.environ.get(name, default))
        except (TypeError, ValueError):
            return default

    def available(self):
        return bool(self.api_key)

    def chat(self, messages, temperature=0.3, max_tokens=900, json_mode=False, timeout=None):
        if not self.api_key:
            raise AIClientError("未配置 AI_API_KEY")

        body = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        url = self.base_url.rstrip("/") + "/chat/completions"
        timeout = timeout or self.timeout
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(body).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + self.api_key,
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                if not content:
                    raise AIClientError("模型返回了空内容")
                return content
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "ignore")[:300]
                last_error = AIClientError(f"HTTP {exc.code}: {detail}")
                if exc.code not in (429, 500, 502, 503, 504):
                    raise last_error
            except Exception as exc:  # 网络超时、解析失败等
                last_error = AIClientError(str(exc))

            if attempt < self.max_retries:
                time.sleep(1.0 * (attempt + 1) ** 2)

        raise last_error or AIClientError("请求失败")