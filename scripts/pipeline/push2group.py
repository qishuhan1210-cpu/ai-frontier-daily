#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
push_feishu_bot.py — §4 群机器人：交互式卡片推送

支持两种推送方式，**使用相同的卡片格式**：
1. 飞书自定义机器人 Webhook（交互式卡片）
2. lark-cli（交互式卡片）

用法:
    # 使用 Webhook 推送交互式卡片
    python3 project-space/push_feishu_bot.py --date 2026-05-11 --doc-url 'https://xxx.feishu.cn/…'
    
    # 使用 lark-cli 推送交互式卡片（格式与 Webhook 一致）
    python3 project-space/push_feishu_bot.py --date 2026-05-11 --doc-url 'https://xxx.feishu.cn/…' --use-lark-cli
"""

from __future__ import annotations

import argparse
import json
import logging
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 设置路径
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_POSTACT_SPACE = _PROJECT_ROOT / 'postact-space'
_PROJECT_SPACE = _PROJECT_ROOT / 'project-space'
for p in (_PROJECT_ROOT, _POSTACT_SPACE, _PROJECT_SPACE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from utils import AppConfig
from utils.logger import get_logger
from utils.lark_commander import LarkCmd


# =============================================================================
# 常量配置
# =============================================================================

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
    protocols: Any
    webhook: list[str] | None
    chat_id: str | None
    use_lark_cli: bool


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

    def __init__(self, config: PushConfig, logger: logging.Logger | None = None):
        self.cfg = config
        self.logger = logger or logging.getLogger('push2group')
        self.footer_modules = {m.id: m.name for m in config.protocols.classification.main_sections}
        self.section_name_to_id = {m.name: m.id for m in config.protocols.classification.main_sections}

    # -------------------------------------------------------------------------
    # 公共接口
    # -------------------------------------------------------------------------

    def push(self) -> PushResult:
        """执行完整推送流程"""
        self.logger.info(f"=== 开始推送飞书群消息 ===")
        self.logger.info(f"推送日期: {self.cfg.date}")
        self.logger.info(f"文档链接: {self.cfg.doc_url}")
        self.logger.info(f"推送方式: {'lark-cli' if self.cfg.use_lark_cli else 'Webhook'}")
        
        try:
            payload = self._build_payload()
            self.logger.info(f"成功构建 payload，共 {len(payload.get('card', {}).get('elements', []))} 个元素")
            
            self._validate_payload(payload)

            if self.cfg.use_lark_cli:
                self.logger.info("通过 lark-cli 发送消息...")
                response = self._send_via_lark_cli(payload)
            else:
                self.logger.info(f"通过 Webhook 发送消息，共 {len(self.cfg.webhook)} 个目标...")
                response = self._send_webhook(payload)

            self.logger.info(f"推送成功")
            return PushResult(success=True, message='推送成功', response=response)
        except FileNotFoundError as e:
            self.logger.error(f"文件不存在: {e}")
            return PushResult(success=False, message=f'文件不存在: {e}')
        except ValueError as e:
            self.logger.error(f"校验失败: {e}")
            return PushResult(success=False, message=f'校验失败: {e}')
        except RuntimeError as e:
            self.logger.error(f"运行时错误: {e}")
            return PushResult(success=False, message=str(e))
        except urllib.error.HTTPError as e:
            self.logger.error(f"HTTP {e.code}: {e.reason}")
            return PushResult(success=False, message=f'HTTP {e.code}: {e.reason}')
        except urllib.error.URLError as e:
            self.logger.error(f"网络错误: {e.reason}")
            return PushResult(success=False, message=f'网络错误: {e.reason}')
        except Exception as e:
            self.logger.error(f"未知错误: {e}")
            return PushResult(success=False, message=f'未知错误: {e}')

    # -------------------------------------------------------------------------
    # 私有方法：Payload 构建
    # -------------------------------------------------------------------------

    def _build_payload(self) -> dict[str, Any]:
        """构建飞书交互式卡片 payload"""
        self.logger.info("=== 构建 payload ===")
        summary = self._load_summary()
        self.logger.info(f"加载 summary.json 成功，共 {len(summary.get('clusters', []))} 个 clusters")
        
        paragraphs = self._build_paragraphs(summary.get('blocks', {}), summary.get('clusters', []))
        self.logger.info(f"构建段落完成，共 {len(paragraphs)} 个段落")

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

    def _build_paragraphs(self, blocks: dict, items: list) -> list[str]:
        """从 blocks.footer 构建段落列表，包含热度标识"""
        footer = blocks.get('footer', {})
        paragraphs = []

        # 计算每个模块的热度标识
        module_hot = self._calculate_module_hot(items)

        for key, label in self.footer_modules.items():
            content = footer.get(key, '')
            if not content or not str(content).strip():
                continue

            lines = [ln.strip() for ln in str(content).splitlines() if ln.strip()]
            if not lines:
                continue

            # 添加热度标识
            hot_mark = module_hot.get(key, '')
            head = f'{label}{hot_mark}：{lines[0]}'
            tail = '\n'.join(lines[1:])
            paragraphs.append(head if not tail else f'{head}\n{tail}')

        return paragraphs

    def _calculate_module_hot(self, items: list) -> dict:
        """计算每个模块的热度标识"""
        module_hot_counts = {key: [] for key in self.footer_modules.keys()}

        for item in items:
            main_section = item.get('main_section', '')
            module_id = self.section_name_to_id.get(main_section)
            if module_id in module_hot_counts:
                hot = item.get('hot', '')
                if hot:
                    fire_count = hot.count('🔥')
                    module_hot_counts[module_id].append(fire_count)

        # 计算每个模块的最高热度
        result = {}
        for module_id, counts in module_hot_counts.items():
            if counts:
                max_fire = max(counts)
                result[module_id] = ' ' + '🔥' * max_fire

        return result

    def _validate_payload(self, payload: dict) -> None:
        """验证 payload 大小"""
        size = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
        if size > MAX_BODY_BYTES:
            raise ValueError(f'请求体 {size} 字节，超过 {MAX_BODY_BYTES} 字节限制')

    # -------------------------------------------------------------------------
    # 私有方法：网络请求
    # -------------------------------------------------------------------------

    def _send_webhook(self, payload: dict) -> dict:
        """发送 webhook 请求（支持多个 webhook）"""
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        results = []
        
        # 创建不验证 SSL 证书的上下文（解决自签名证书问题）
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        for webhook_url in self.cfg.webhook:
            req = urllib.request.Request(
                webhook_url,
                data=body,
                headers={'Content-Type': 'application/json; charset=utf-8'},
                method='POST',
            )
            with urllib.request.urlopen(req, context=ssl_context, timeout=30.0) as resp:
                raw = resp.read().decode('utf-8')
                results.append(json.loads(raw) if raw.strip() else {})
        
        # 返回最后一个成功的响应，或合并所有响应
        return results[-1] if results else {}

    def _send_via_lark_cli(self, payload: dict) -> dict:
        """使用 lark-cli 发送交互式卡片"""
        chat_id = self.cfg.chat_id
        if not chat_id:
            chat_id = self._load_chat_id_from_secrets()

        if not chat_id:
            raise ValueError('缺少 chat-id 配置')

        content = json.dumps(payload['card'], ensure_ascii=False)
        message_id = LarkCmd.IM_MESSAGE_SEND.args(
            chat_id=chat_id,
            content=content
        ).run(logger=self.logger)

        if message_id is None:
            raise RuntimeError('lark-cli 推送失败')

        # 返回消息 ID 响应
        return {'message_id': message_id} if message_id else {}

    def _load_chat_id_from_secrets(self) -> str | None:
        """从 secrets.json 加载 chat_id"""
        return AppConfig()._feishu_config.get('chat_id', '').strip()


# =============================================================================
# 配置工厂
# =============================================================================

class ConfigFactory:
    """从各种来源创建 PushConfig"""

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> PushConfig:
        """从命令行参数创建配置"""
        date = args.date
        app_config = AppConfig(date_str=date)

        webhook = cls._load_webhooks_from_secrets(app_config) if not args.use_lark_cli else None
        chat_id = args.chat_id or cls._load_chat_id_from_secrets(app_config) if args.use_lark_cli else None
        summary_path = cls._resolve_summary_path(app_config, args.summary_json)

        return PushConfig(
            date=date,
            doc_url=args.doc_url,
            summary_path=summary_path,
            protocols=app_config.protocols,
            webhook=webhook,
            chat_id=chat_id,
            use_lark_cli=args.use_lark_cli,
        )

    @staticmethod
    def _load_webhooks_from_secrets(app_config: AppConfig) -> list[str]:
        """从 secrets.json 加载 webhooks（兼容新旧配置并去重）"""
        feishu_cfg = app_config._feishu_config
        
        # 收集所有 webhook
        all_webhooks = []
        
        # 读取旧配置（字符串形式）
        old_webhook = feishu_cfg.get('bot_webhook', '').strip()
        if old_webhook:
            all_webhooks.append(old_webhook)
        
        # 读取新配置（数组形式）
        new_webhooks = feishu_cfg.get('bot_webhooks', [])
        if isinstance(new_webhooks, list):
            for w in new_webhooks:
                w_stripped = w.strip()
                if w_stripped:
                    all_webhooks.append(w_stripped)
        
        # 去重处理（保持顺序）
        seen = set()
        result = []
        for w in all_webhooks:
            if w not in seen:
                seen.add(w)
                result.append(w)
        
        if not result:
            raise ValueError('config/secrets.json 缺少 feishu.bot_webhooks 或 feishu.bot_webhook 配置')
        
        return result

    @staticmethod
    def _load_chat_id_from_secrets(app_config: AppConfig) -> str | None:
        """从 secrets.json 加载 chat_id"""
        return app_config._feishu_config.get('chat_id', '').strip()

    @staticmethod
    def _resolve_summary_path(app_config: AppConfig, custom_path: str | None) -> Path:
        """解析 summary.json 路径"""
        if custom_path:
            path = Path(custom_path)
        else:
            path = app_config.paths.day_paths()['summary']

        if not path.exists():
            raise FileNotFoundError(f'找不到 {path}')
        return path


# =============================================================================
# CLI 入口
# =============================================================================

def create_parser() -> argparse.ArgumentParser:
    """创建参数解析器"""
    parser = argparse.ArgumentParser(
        description='飞书推送：AI 前沿早报（支持 Webhook 和 lark-cli 两种方式）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例:
  # 使用 Webhook 推送交互式卡片
  %(prog)s --date 2026-05-11 --doc-url 'https://xxx.feishu.cn/...'
  
  # 使用 lark-cli 推送交互式卡片（格式与 Webhook 一致）
  %(prog)s --date 2026-05-11 --doc-url 'https://xxx.feishu.cn/...' --use-lark-cli
  
  # 指定 chat-id
  %(prog)s --date 2026-05-11 --doc-url 'https://xxx.feishu.cn/...' --use-lark-cli --chat-id oc_xxx
        '''.strip()
    )
    parser.add_argument('--date', required=True, help='日期 (YYYY-MM-DD)')
    parser.add_argument('--doc-url', required=True, help='飞书文档 URL')
    parser.add_argument('--summary-json', help='自定义 summary.json 路径')
    parser.add_argument('--use-lark-cli', action='store_true', help='使用 lark-cli 推送（默认使用 Webhook）')
    parser.add_argument('--chat-id', help='飞书群聊 ID（使用 lark-cli 时必填，或在 secrets.json 中配置）')
    return parser


def main() -> int:
    """主入口"""
    parser = create_parser()
    args = parser.parse_args()

    logger = get_logger('push2group', args.date)
    sep = "=" * 63
    logger.info(sep)
    logger.info("=== 飞书群推送脚本启动 ===")
    logger.info(f"日期: {args.date}")
    logger.info(f"文档URL: {args.doc_url}")
    logger.info(sep)
    
    try:
        config = ConfigFactory.from_args(args)
    except (ValueError, FileNotFoundError) as e:
        logger.error(f"配置错误: {e}")
        return 1

    pusher = FeishuBotPusher(config, logger)
    result = pusher.push()

    if result.success:
        logger.info(f"=== 推送完成 ===")
        logger.info(f"success: {result.message}")
        if result.response:
            logger.info(json.dumps(result.response, ensure_ascii=False, indent=2))
        return 0
    else:
        logger.error(f"=== 推送失败 ===")
        logger.error(f"error: {result.message}")
        return 1


if __name__ == '__main__':
    sys.exit(main())