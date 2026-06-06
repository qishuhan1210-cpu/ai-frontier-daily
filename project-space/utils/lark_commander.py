"""LarkCommander — 桥接层，根据配置动态选择实现"""

from __future__ import annotations
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import json
import logging

# 配置日志
logger = logging.getLogger(__name__)

_LARK_CLI = shutil.which('lark-cli') or 'lark-cli'


class _LarkCommand:
    """lark-cli 命令实例（由 LarkCmd.args() 创建）"""

    def __init__(self, template: list[str]):
        self._template = template
        self._kwargs: dict = {}
        self._input_text: Optional[str] = None

    def args(self, **kwargs) -> '_LarkCommand':
        """设置命令模板中的占位符参数"""
        self._kwargs.update(kwargs)
        return self

    def input(self, text: str) -> '_LarkCommand':
        """设置 stdin 输入内容（如文档正文）"""
        self._input_text = text
        return self

    def run(self, logger=None) -> Optional[str]:
        """执行 lark-cli 命令

        Args:
            logger: 可选 logger 实例，用于记录错误日志

        Returns:
            命令执行成功返回 stdout（去除空白和 'null'），失败返回 None
        """
        cmd_args = [arg.format(**self._kwargs) for arg in self._template]

        result = subprocess.run(
            [_LARK_CLI] + cmd_args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            input=self._input_text
        )

        if result.returncode != 0:
            msg = f"命令执行失败: {' '.join(cmd_args)}"
            if result.stderr:
                msg += f" - {result.stderr.strip()}"
            if logger:
                logger.error(msg)
            return None

        output = result.stdout.strip()
        return output if output and output != 'null' else None


def _get_use_sdk() -> bool:
    """从配置文件读取是否使用 SDK 模式"""
    project_root = Path(__file__).parent.parent.parent
    secrets_path = project_root / 'config' / 'secrets.json'
    
    try:
        with open(secrets_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            feishu_config = config.get('feishu', {})
            return feishu_config.get('use_sdk', False)
    except Exception as e:
        logger.warning(f"读取配置失败，默认使用 SDK 模式: {e}")
        return True


# 根据配置选择实现
if _get_use_sdk():
    # 使用 Python SDK 实现
    try:
        from .lark_sdk_commander import LarkCmd, LarkClient, LarkSdkCommand
        
        # 辅助函数桥接（如有需要）
        def get_lark_client():
            return LarkClient()

        logger.info("LarkCommander: 已切换至 Python SDK 实现（带自动刷新功能）")
        
        # SDK 模式下直接导出，不再定义 LarkCmd 类
        __all__ = ['LarkCmd', 'get_lark_client']
        
    except ImportError as e:
        # SDK 模块不可用，回退至 CLI 模式
        logger.error(f"LarkCommander: SDK 导入失败 ({e})，回退至 CLI 模式")
        use_sdk = False
else:
    # 配置指定使用 CLI 模式
    logger.info("LarkCommander: 配置指定使用 CLI 模式")
    use_sdk = False


# CLI 模式实现（如果上面没有使用 SDK）
if 'use_sdk' in locals() and not use_sdk:
    import subprocess

    class _LarkCommand:
        """lark-cli 命令实例（回退模式）"""
        
        # 需要过滤内部字段的命令列表
        _FILTER_COMMANDS = {'base', '+record-batch-create'}
        
        def __init__(self, template: list[str]):
            self._template = template
            self._kwargs: dict = {}
            self._input_text: Optional[str] = None

        def args(self, **kwargs) -> '_LarkCommand':
            self._kwargs.update(kwargs)
            return self

        def input(self, text: str) -> '_LarkCommand':
            self._input_text = text
            return self
        
        def _filter_internal_fields(self, kwargs: dict) -> dict:
            """过滤 SDK 模式专用的内部字段，避免 CLI 模式下传递给 API"""
            filtered = kwargs.copy()
            
            # 检查是否是需要过滤的命令
            cmd_str = ' '.join(self._template)
            if '+record-batch-create' in cmd_str:
                data_json = kwargs.get('data_json')
                if data_json:
                    try:
                        data = json.loads(data_json)
                        # 移除 SDK 专用的内部字段
                        if isinstance(data, dict) and 'field_types' in data:
                            data = {k: v for k, v in data.items() if k != 'field_types'}
                            filtered['data_json'] = json.dumps(data, ensure_ascii=False)
                    except json.JSONDecodeError:
                        pass
            
            return filtered

        def run(self, logger=None) -> Optional[str]:
            # 过滤内部字段（仅 CLI 模式需要）
            filtered_kwargs = self._filter_internal_fields(self._kwargs)
            cmd_args = [arg.format(**filtered_kwargs) for arg in self._template]
            
            result = subprocess.run(
                [_LARK_CLI] + cmd_args,
                capture_output=True,
                text=True,
                encoding='utf-8',
                input=self._input_text
            )
            if result.returncode != 0:
                if logger: logger.error(f"CLI 回退执行失败: {result.stderr}")
                return None
            output = result.stdout.strip()
            return output if output and output != 'null' else None


    class LarkCmd:
        """lark-cli 命令模板（静态工厂）"""

        # === Wiki 命令 ===
        WIKI_NODE_LIST = _LarkCommand(['wiki', '+node-list', '--as', 'user', '--space-id', '{space_id}', '--page-all', '-q', '{query}'])
        WIKI_NODE_LIST_BY_PARENT = _LarkCommand(['wiki', '+node-list', '--as', 'user', '--space-id', '{space_id}', '--parent-node-token', '{parent_token}', '--page-all', '-q', '{query}'])
        WIKI_NODE_SEARCH_BITABLE = _LarkCommand(['wiki', '+node-list', '--as', 'user', '--space-id', '{space_id}', '--page-all', '-q', '.data.nodes[] | select(.obj_type == "bitable" and (.title | contains("{keyword}"))) | {{node_token: .node_token, obj_token: .obj_token, title: .title}}'])
        WIKI_NODE_CREATE = _LarkCommand(['wiki', '+node-create', '--as', 'user', '--space-id', '{space_id}', '--obj-type', 'docx', '--title', '{title}', '-q', '.data.node_token'])
        WIKI_NODE_CREATE_WITH_PARENT = _LarkCommand(['wiki', '+node-create', '--as', 'user', '--space-id', '{space_id}', '--title', '{title}', '--parent-node-token', '{parent_token}', '-q', '.data.node_token'])
        WIKI_NODE_MOVE = _LarkCommand(['wiki', '+move', '--as', 'user', '--node-token', '{node_token}', '--target-parent-token', '{target_parent_token}'])

        # === Docs 命令 ===
        DOC_UPDATE = _LarkCommand(['docs', '+update', '--api-version', 'v1', '--as', 'user', '--doc', '{doc_token}', '--new-title', '{title}', '--mode', 'overwrite', '--markdown', '-'])

        # === Base 命令 ===
        BASE_CREATE = _LarkCommand(['base', '+base-create', '--name', '{name}', '--time-zone', '{timezone}', '--format', 'json', '-q', '.data.base.base_token'])
        BASE_TABLE_LIST = _LarkCommand(['base', '+table-list', '--base-token', '{base_token}', '-q', '.data.tables'])
        BASE_TABLE_CREATE = _LarkCommand(['base', '+table-create', '--base-token', '{base_token}', '--json', '{table_json}', '--format', 'json', '-q', '.data.table.id'])
        BASE_FIELD_LIST = _LarkCommand(['base', '+field-list', '--base-token', '{base_token}', '--table-id', '{table_id}', '-q', '[.data.fields[] | {{field_id: .id, name: .name, type: .type}}]'])
        BASE_FIELD_CREATE = _LarkCommand(['base', '+field-create', '--base-token', '{base_token}', '--table-id', '{table_id}', '--json', '{field_json}', '-q', '.data.field.id'])
        BASE_RECORD_SEARCH = _LarkCommand(['base', '+record-search', '--base-token', '{base_token}', '--table-id', '{table_id}', '--json', '{search_json}', '--format', 'json'])
        BASE_RECORD_DELETE = _LarkCommand(['base', '+record-delete', '--base-token', '{base_token}', '--table-id', '{table_id}', '--json', '{delete_json}', '--yes', '-q', '.data.deleted_record_id_list'])
        BASE_RECORD_BATCH_CREATE = _LarkCommand(['base', '+record-batch-create', '--base-token', '{base_token}', '--table-id', '{table_id}', '--json', '{data_json}', '-q', '.data.record_id_list'])

        # === IM 命令 ===
        IM_MESSAGE_SEND = _LarkCommand(['im', '+messages-send', '--chat-id', '{chat_id}', '--msg-type', 'interactive', '--content', '{content}'])
