#!/usr/bin/env python3
"""LLM 客户端 - 统一的 OpenAI 兼容 API 调用"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from utils.base_config import load_llm_config


class LLMClient:
    """LLM 客户端 - 封装 OpenAI 兼容 API 调用"""

    def __init__(self):
        self._config: dict[str, Any] | None = None
        self._client: Any | None = None

    def _load_config(self) -> dict[str, Any] | None:
        """加载 LLM 配置"""
        if self._config is not None:
            return self._config
        self._config = load_llm_config()
        return self._config

    def _get_client(self) -> Any | None:
        """获取 OpenAI 客户端实例"""
        if self._client is not None:
            return self._client

        cfg = self._load_config()
        if not cfg:
            print("[LLMClient] 错误: 无法加载 LLM 配置")
            return None

        api_key = cfg.get("api_key")
        base_url = cfg.get("base_url")
        model_name = cfg.get("model_name")

        if not all([api_key, base_url, model_name]):
            print(f"[LLMClient] 错误: 配置不完整 (api_key={bool(api_key)}, base_url={bool(base_url)}, model_name={bool(model_name)})")
            return None

        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key, base_url=base_url)
            print(f"[LLMClient] 已初始化: {model_name}")
            return self._client
        except Exception as e:
            print(f"[LLMClient] 错误: 客户端初始化失败: {e}")
            return None

    def call(self, system: str, user: str, temperature: float = 0.3, max_tokens: int = 2000) -> str:
        """调用 LLM，返回文本（失败时抛异常）"""
        client = self._get_client()
        cfg = self._load_config()
        model = cfg["model_name"]

        # 计算输入 token 数量（粗略估算）
        input_tokens = len(system) + len(user)
        print(f"[LLMClient] 请求: model={model}, temp={temperature}, max_tokens={max_tokens}, 输入约 {input_tokens} 字符")

        start_time = time.time()
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            elapsed = time.time() - start_time
            output_tokens = len(resp.choices[0].message.content) if resp.choices else 0
            print(f"[LLMClient] 响应: 耗时 {elapsed:.2f}s, 输出约 {output_tokens} 字符")
            return resp.choices[0].message.content
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[LLMClient] 失败: 耗时 {elapsed:.2f}s, 错误: {e}")
            raise RuntimeError(f"LLM 调用失败: {e}") from e

    def call_json(self, system: str, user: str, temperature: float = 0.3, max_tokens: int = 20480) -> dict[str, Any]:
        """调用 LLM，自动解析 JSON 返回（解析失败时抛异常）"""
        content = self.call(system, user, temperature, max_tokens)

        # 尝试从 markdown 代码块提取
        if match := re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', content):
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试直接解析任意 JSON 对象
        if match := re.search(r'\{[\s\S]*\}', content):
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 尝试直接解析整个内容
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"LLM 返回内容 JSON 解析失败: {e}\n内容片段: {content[:200]}...") from e


# 模块级便捷函数
def call_llm(system: str, user: str, temperature: float = 0.3, max_tokens: int = 2000) -> str | None:
    """调用 LLM（便捷函数）"""
    return LLMClient().call(system, user, temperature, max_tokens)


def call_llm_json(system: str, user: str, temperature: float = 0.3, max_tokens: int = 20480) -> dict[str, Any] | None:
    """调用 LLM 并解析 JSON（便捷函数）"""
    return LLMClient().call_json(system, user, temperature, max_tokens)


__all__ = ["LLMClient", "call_llm", "call_llm_json"]
