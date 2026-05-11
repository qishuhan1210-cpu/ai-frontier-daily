#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_feishu_bot.py — §4 群机器人：交互式卡片推送

组装 `msg_type: interactive` 请求体，POST 至飞书自定义机器人 Webhook。

用法:
    python3 project-space/push_feishu_bot.py --date 2026-05-04 --doc-url 'https://xxx.feishu.cn/…'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 设置路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_SPACE = _PROJECT_ROOT / 'project-space'
for p in (_PROJECT_ROOT, _PROJECT_SPACE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from utils.base_config import default_day_paths, load_assembly_config, load_secrets


# =============================================================================
# 常量配置
# =============================================================================

# footer 字段顺序与模块中文简称映射
FOOTER_MODULES = {
    'hardware': '硬件',
    'model': '模型',
    'application': '应用',
    'investment': '投融资',
    'policy': '政策',
}
MAX_BODY_BYTES = 20 * 1024


# =============================================================================
# 数据类
# =============================================================================

@dataclass(frozen=True)
class PushConfig:
    """推送配置"""
    date: str
    doc_url: str
    summary_path: Path
    webhook: str


@dataclass(frozen=True)
class PushResult:
    """推送结果"""
    success: bool
    message: str
    response: dict | None = None


# =============================================================================
# 核心类
# =============================================================================

class FeishuBotPusher:
    """飞书机器人推送器"""

    def __init__(self, config: PushConfig):
        self.cfg = config

    # -------------------------------------------------------------------------
    # 公共接口
    # -------------------------------------------------------------------------

    def push(self) -> PushResult:
        """执行完整推送流程"""
        try:
            payload = self._build_payload()
            self._validate_payload(payload)
            response = self._send_webhook(payload)
            return PushResult(success=True, message='推送成功', response=response)
        except FileNotFoundError as e:
            return PushResult(success=False, message=f'文件不存在: {e}')
        except ValueError as e:
            return PushResult(success=False, message=f'校验失败: {e}')
        except urllib.error.HTTPError as e:
            return PushResult(success=False, message=f'HTTP {e.code}: {e.reason}')
        except urllib.error.URLError as e:
            return PushResult(success=False, message=f'网络错误: {e.reason}')
        except Exception as e:
            return PushResult(success=False, message=f'未知错误: {e}')

    # -------------------------------------------------------------------------
    # 私有方法：Payload 构建
    # -------------------------------------------------------------------------

    def _build_payload(self) -> dict[str, Any]:
        """构建飞书交互式卡片 payload"""
        summary = self._load_summary()
        paragraphs = self._build_paragraphs(summary.get('blocks', {}))

        elements = [
            {'tag': 'div', 'text': {'tag': 'lark_md', 'content': p}}
            for p in paragraphs
        ] or [{'tag': 'div', 'text': {'tag': 'lark_md', 'content': '（暂无摘要内容）'}}]

        elements.append({
            'tag': 'action',
            'actions': [{
                'tag': 'button',
                'text': {'tag': 'plain_text', 'content': '立即查看'},
                'type': 'primary',
                'url': self.cfg.doc_url,
            }]
        })

        return {
            'msg_type': 'interactive',
            'card': {
                'header': {
                    'title': {'tag': 'plain_text', 'content': f'AI 前沿早报（{self.cfg.date}）'},
                    'template': 'blue',
                },
                'elements': elements,
            },
        }

    def _load_summary(self) -> dict:
        """加载 summary.json"""
        with open(self.cfg.summary_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _build_paragraphs(self, blocks: dict) -> list[str]:
        """从 blocks.footer 构建段落列表"""
        footer = blocks.get('footer', {})
        paragraphs = []

        for key, label in FOOTER_MODULES.items():
            content = footer.get(key, '')
            if not content or not str(content).strip():
                continue

            lines = [ln.strip() for ln in str(content).splitlines() if ln.strip()]
            if not lines:
                continue

            head = f'{label}：{lines[0]}'
            tail = '\n'.join(lines[1:])
            paragraphs.append(head if not tail else f'{head}\n{tail}')

        return paragraphs

    def _validate_payload(self, payload: dict) -> None:
        """验证 payload 大小"""
        size = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        if size > MAX_BODY_BYTES:
            raise ValueError(f'请求体 {size} 字节，超过 {MAX_BODY_BYTES} 字节限制')

    # -------------------------------------------------------------------------
    # 私有方法：网络请求
    # -------------------------------------------------------------------------

    def _send_webhook(self, payload: dict) -> dict:
        """发送 webhook 请求"""
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            self.cfg.webhook,
            data=body,
            headers={'Content-Type': 'application/json; charset=utf-8'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            raw = resp.read().decode('utf-8')
            return json.loads(raw) if raw.strip() else {}


# =============================================================================
# 配置工厂
# =============================================================================

class ConfigFactory:
    """从各种来源创建 PushConfig"""

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> PushConfig:
        """从命令行参数创建配置"""
        webhook = cls._load_webhook_from_secrets()
        summary_path = cls._resolve_summary_path(args.date, args.summary_json)

        return PushConfig(
            date=args.date,
            doc_url=args.doc_url,
            summary_path=summary_path,
            webhook=webhook,
        )

    @staticmethod
    def _load_webhook_from_secrets() -> str:
        """从 secrets.json 加载 webhook"""
        secrets = load_secrets()
        webhook = secrets.get('feishu', {}).get('bot_webhook', '').strip()
        if not webhook:
            raise ValueError('config/secrets.json 缺少 feishu.bot_webhook 配置')
        return webhook

    @staticmethod
    def _resolve_summary_path(date: str, custom_path: str | None) -> Path:
        """解析 summary.json 路径"""
        if custom_path:
            path = Path(custom_path)
        else:
            path = default_day_paths(date)['summary']

        if not path.exists():
            raise FileNotFoundError(f'找不到 {path}')
        return path


# =============================================================================
# CLI 入口
# =============================================================================

def create_parser() -> argparse.ArgumentParser:
    """创建参数解析器"""
    parser = argparse.ArgumentParser(
        description='飞书自定义机器人：推送 AI 前沿早报交互式卡片',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  %(prog)s --date 2026-05-11 --doc-url 'https://xxx.feishu.cn/...'
        '''.strip()
    )
    parser.add_argument('--date', required=True, help='日期 (YYYY-MM-DD)')
    parser.add_argument('--doc-url', required=True, help='飞书文档 URL')
    parser.add_argument('--summary-json', help='自定义 summary.json 路径')
    return parser


def main() -> int:
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()

    try:
        config = ConfigFactory.from_args(args)
    except (ValueError, FileNotFoundError) as e:
        print(f'error: {e}', file=sys.stderr)
        return 1

    pusher = FeishuBotPusher(config)
    result = pusher.push()

    if result.success:
        print(json.dumps(result.response, ensure_ascii=False, indent=2))
        return 0
    else:
        print(f'error: {result.message}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
