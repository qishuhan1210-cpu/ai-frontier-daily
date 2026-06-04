#!/usr/bin/env python3
"""llm_client.py 测试"""

import json
import re
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
import sys

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from utils.llm_client import LLMClient


class TestLLMClient:
    """LLMClient 测试"""

    def test_init(self):
        """测试初始化"""
        cfg = {'api_key': 'test_key', 'base_url': 'http://test.com', 'model_name': 'gpt-4'}
        client = LLMClient(cfg, '2026-05-23')
        assert client._cfg == cfg
        assert client._client is None

    def test_get_client_invalid_config(self):
        """测试配置不完整的情况"""
        cfg = {'api_key': '', 'base_url': '', 'model_name': ''}
        client = LLMClient(cfg, '2026-05-23')
        result = client._get_client()
        assert result is None

    def test_get_client_missing_fields(self):
        """测试缺少必要配置字段"""
        cfg = {'api_key': 'test_key'}
        client = LLMClient(cfg, '2026-05-23')
        result = client._get_client()
        assert result is None

    def test_call_json_extraction(self):
        """测试 JSON 提取逻辑（不需要调用 OpenAI）"""
        cfg = {'api_key': 'test_key', 'base_url': 'http://test.com', 'model_name': 'gpt-4'}
        client = LLMClient(cfg, '2026-05-23')
        
        # 让我们创建一个 mock 来测试 call_json 的解析部分
        with patch.object(client, 'call') as mock_call:
            # 测试带代码块的情况
            mock_call.return_value = '```json\n{"test": "value"}\n```'
            result = client.call_json('system prompt', 'user prompt')
            assert result == {'test': 'value'}
            
            # 测试不带代码块的情况
            mock_call.return_value = '{"test": "value"}'
            result = client.call_json('system prompt', 'user prompt')
            assert result == {'test': 'value'}
            
            # 测试解析失败的情况
            mock_call.return_value = 'not a json'
            with pytest.raises(RuntimeError):
                client.call_json('system prompt', 'user prompt')
    
    def test_call_json_with_other_json_patterns(self):
        """测试其他 JSON 模式的提取"""
        cfg = {'api_key': 'test_key', 'base_url': 'http://test.com', 'model_name': 'gpt-4'}
        client = LLMClient(cfg, '2026-05-23')
        
        with patch.object(client, 'call') as mock_call:
            # 测试其他 JSON 格式
            mock_call.return_value = 'Here is the data: {"key": "val"}'
            result = client.call_json('system prompt', 'user prompt')
            assert result == {'key': 'val'}

    def test_fix_json_escaping_normal_json(self):
        """测试正常 JSON 不被修改"""
        cfg = {'api_key': 'test_key', 'base_url': 'http://test.com', 'model_name': 'gpt-4'}
        client = LLMClient(cfg, '2026-05-23')
        
        # 正常 JSON 应该保持不变
        test_cases = [
            '{"key": "value"}',
            '{"name": "test", "count": 123}',
            '{"text": "hello world"}',
            '{}',
        ]
        
        for test_input in test_cases:
            result = client._fix_json_escaping(test_input)
            assert result == test_input, f"正常 JSON 被错误修改: {test_input} -> {result}"
            # 确保可以解析
            json.loads(result)

    def test_fix_json_escaping_double_quotes_in_string(self):
        """测试 LLM 输出的连续双引号转义（"" 表示 "）"""
        cfg = {'api_key': 'test_key', 'base_url': 'http://test.com', 'model_name': 'gpt-4'}
        client = LLMClient(cfg, '2026-05-23')
        
        # 测试场景：LLM 输出 "" 表示转义的 "
        # 例如：{"text": ""含欧量"要求"} 应该转换为 {"text": "\"含欧量\"要求"}
        test_cases = [
            # (输入, 期望输出, 期望解析结果)
            ('{"text": ""quoted""}', '{"text": "\\"quoted\\""}', {'text': '"quoted"'}),
            ('{"impacts": ["正常文本", ""含欧量"要求"]}', 
             '{"impacts": ["正常文本", "\\"含欧量\\"要求"]}', 
             {'impacts': ['正常文本', '"含欧量"要求']}),
        ]
        
        for test_input, expected_output, expected_parse in test_cases:
            result = client._fix_json_escaping(test_input)
            assert result == expected_output, f"转义失败: {test_input} -> {result}"
            # 确保可以解析
            parsed = json.loads(result)
            assert parsed == expected_parse, f"解析结果不匹配: {parsed} != {expected_parse}"

    def test_fix_json_escaping_single_quotes_in_string(self):
        """测试字符串中间单个双引号的转义（修复后应该能正确解析）"""
        cfg = {'api_key': 'test_key', 'base_url': 'http://test.com', 'model_name': 'gpt-4'}
        client = LLMClient(cfg, '2026-05-23')
        
        # 测试场景：字符串中间的单个双引号需要被转义
        test_cases = [
            # {"text": "hello"world"} 应该转换为 {"text": "hello\"world"}
            ('{"text": "hello"world"}', '{"text": "hello\\"world"}', {'text': 'hello"world'}),
            ('{"text": "start"middle"end"}', '{"text": "start\\"middle\\"end"}', {'text': 'start"middle"end'}),
            ('{"content": "测试"数据"}', '{"content": "测试\\"数据"}', {'content': '测试"数据'}),
            # 多个双引号的情况
            ('{"text": "hello"world"xxxx"}', '{"text": "hello\\"world\\"xxxx"}', {'text': 'hello"world"xxxx'}),
        ]
        
        for test_input, expected_output, expected_parse in test_cases:
            result = client._fix_json_escaping(test_input)
            assert result == expected_output, f"转义失败: {test_input} -> {result}"
            # 确保可以解析
            parsed = json.loads(result)
            assert parsed == expected_parse, f"解析结果不匹配: {parsed} != {expected_parse}"

    def test_fix_json_escaping_edge_cases(self):
        """测试边界情况"""
        cfg = {'api_key': 'test_key', 'base_url': 'http://test.com', 'model_name': 'gpt-4'}
        client = LLMClient(cfg, '2026-05-23')
        
        # 空字符串
        assert client._fix_json_escaping('') == ''
        
        # 只有双引号
        assert client._fix_json_escaping('""') == '""'
        
        # 连续四个双引号
        test_input = '{"text": """"}'
        result = client._fix_json_escaping(test_input)
        # """" 在字符串内应该变成 \\"" (两个转义的双引号)
        assert result == '{"text": "\\"\\""}'
        parsed = json.loads(result)
        assert parsed == {'text': '""'}

    def test_fix_json_escaping_already_escaped(self):
        """测试已经正确转义的 JSON"""
        cfg = {'api_key': 'test_key', 'base_url': 'http://test.com', 'model_name': 'gpt-4'}
        client = LLMClient(cfg, '2026-05-23')
        
        test_cases = [
            '{"text": "hello\\"world"}',  # 已经转义的双引号
            '{"text": "line1\\nline2"}',  # 其他转义字符
            '{"text": "\\\\test"}',       # 转义的反斜杠
        ]
        
        for test_input in test_cases:
            result = client._fix_json_escaping(test_input)
            assert result == test_input, f"已转义的 JSON 被错误修改: {test_input} -> {result}"
            json.loads(result)
