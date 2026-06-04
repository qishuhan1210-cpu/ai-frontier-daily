#!/usr/bin/env python3
"""LLM 客户端 - 统一的 OpenAI 兼容 API 调用"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from .logger import get_logger


class LLMClient:
    """LLM 客户端 - 封装 OpenAI 兼容 API 调用"""

    def __init__(self, llm_cfg: dict[str, Any], date: str = None):
        self._cfg = llm_cfg
        self._client: Any | None = None
        self._logger = get_logger('llm_client', date or time.strftime('%Y-%m-%d'))

    def _get_client(self) -> Any | None:
        """获取 OpenAI 客户端实例"""
        if self._client is not None:
            return self._client

        cfg = self._cfg
        if not cfg:
            self._logger.error("无法加载 LLM 配置")
            return None

        api_key = cfg.get("api_key")
        base_url = cfg.get("base_url")
        model_name = cfg.get("model_name")

        if not all([api_key, base_url, model_name]):
            self._logger.error(f"配置不完整 (api_key={bool(api_key)}, base_url={bool(base_url)}, model_name={bool(model_name)})")
            return None

        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=api_key, base_url=base_url)
            self._logger.info(f"已初始化: {model_name}")
            return self._client
        except Exception as e:
            self._logger.error(f"客户端初始化失败: {e}")
            return None

    def call(self, system: str, user: str, temperature: float | None = None, max_tokens: int | None = None) -> str:
        """调用 LLM，返回文本（失败时抛异常）"""
        if temperature is None:
            temperature = self._cfg.get('default_temperature', 0.3)
        if max_tokens is None:
            max_tokens = self._cfg.get('default_max_tokens', 2000)
        client = self._get_client()
        model = self._cfg["model_name"]

        input_tokens = len(system) + len(user)
        self._logger.info(f"请求: model={model}, temp={temperature}, max_tokens={max_tokens}, 输入约 {input_tokens} 字符")

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
            self._logger.info(f"响应: 耗时 {elapsed:.2f}s, 输出约 {output_tokens} 字符")
            return resp.choices[0].message.content
        except Exception as e:
            elapsed = time.time() - start_time
            self._logger.error(f"失败: 耗时 {elapsed:.2f}s, 错误: {e}")
            raise RuntimeError(f"LLM 调用失败: {e}") from e

    def _fix_json_escaping(self, content: str) -> str:
        """修复 LLM 返回的 JSON 中常见的转义问题，特别是字符串内未转义的双引号"""
        if not content:
            return content
        
        result = []
        i = 0
        in_string = False
        escape_next = False
        
        while i < len(content):
            char = content[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                result.append(char)
                escape_next = True
                i += 1
                continue
            
            if char == '"':
                if in_string:
                    # 检查后面第一个非空白字符
                    remaining = content[i+1:]
                    j = 0
                    while j < len(remaining) and remaining[j].isspace():
                        j += 1
                    
                    # 如果后面不是结构字符（},] :），则说明这是字符串内容中的双引号，需要转义
                    if j < len(remaining) and remaining[j] not in '},]:':
                        result.append('\\')
                    else:
                        # 不需要转义，是字符串结束符
                        in_string = False
                else:
                    # 进入字符串模式
                    in_string = True
            
            result.append(char)
            i += 1
        
        return ''.join(result)

    def call_json(self, system: str, user: str, temperature: float | None = None, max_tokens: int | None = None) -> dict[str, Any]:
        """调用 LLM，自动解析 JSON 返回（解析失败时抛异常）"""
        if temperature is None:
            temperature = self._cfg.get('default_temperature', 0.3)
        if max_tokens is None:
            max_tokens = self._cfg.get('default_max_tokens', 20480)
        content = self.call(system, user, temperature, max_tokens)

        extracted_content = None
        error_info = []
        
        # 修复策略：先尝试原始内容，如果失败再尝试修复转义问题
        candidates = [content]
        candidates.append(self._fix_json_escaping(content))

        for attempt, candidate in enumerate(candidates, 1):
            if match := re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', candidate):
                extracted_content = match.group(1)
                error_info.append(f"尝试解析代码块中的 JSON{'(修复后)' if attempt > 1 else ''}")
                try:
                    return json.loads(extracted_content)
                except json.JSONDecodeError as e:
                    error_info.append(f"代码块解析失败: {e}")

            if match := re.search(r'\{[\s\S]*\}', candidate):
                extracted_content = match.group()
                error_info.append(f"尝试解析大括号包围的内容{'(修复后)' if attempt > 1 else ''}")
                try:
                    return json.loads(extracted_content)
                except json.JSONDecodeError as e:
                    error_info.append(f"大括号内容解析失败: {e}")

            extracted_content = candidate
            error_info.append(f"尝试解析原始内容{'(修复后)' if attempt > 1 else ''}")
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as e:
                if attempt == len(candidates):
                    self._logger.error(f"JSON 解析失败详情:")
                    self._logger.error(f"  错误类型: {type(e).__name__}")
                    self._logger.error(f"  错误位置: 第 {e.lineno} 行, 第 {e.colno} 列")
                    self._logger.error(f"  错误原因: {e.msg}")
                    self._logger.error(f"  解析尝试: {' → '.join(error_info)}")
                    self._logger.error(f"  内容长度: {len(content)} 字符")
                    
                    context_start = max(0, e.pos - 50) if hasattr(e, 'pos') else max(0, (e.lineno-1)*80 - 50)
                    context_end = min(len(content), context_start + 200)
                    context = content[context_start:context_end]
                    self._logger.error(f"  错误位置上下文 ({context_start}-{context_end}):")
                    self._logger.error(f"    ...{context}...")
                    
                    self._logger.error(f"  完整内容前500字符:")
                    self._logger.error(f"    {content[:500]}")
                    
                    if len(content) > 500:
                        self._logger.error(f"  完整内容后500字符:")
                        self._logger.error(f"    {content[-500:]}")

                    raise RuntimeError(f"LLM 返回内容 JSON 解析失败: {e}") from e