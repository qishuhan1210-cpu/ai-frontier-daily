#!/usr/bin/env python3
"""base_config.py — 统一配置管理（三层架构精简版）"""

import yaml
from pathlib import Path

# === 路径常量 ===
_PROJECT_SPACE = Path(__file__).resolve().parent.parent
PROJECT_ROOT = _PROJECT_SPACE.parent
SECRETS_JSON = PROJECT_ROOT / 'config' / 'secrets.json'

# --- 配置文件 ---
CONFIG_DIR = _PROJECT_SPACE / 'config'
CONFIG_YAML = CONFIG_DIR / 'config.yaml'
TEMPLATE_BRIEFING = CONFIG_DIR / 'briefing-template.md.j2'

# --- 模板文件名称 ---
PROMPTS_DIR = _PROJECT_SPACE / 'prompts'
TEMPLATE_FILTER_RANK = PROMPTS_DIR / 'filter_ranker.md.j2'
TEMPLATE_SUMMARIZE = PROMPTS_DIR / 'summarizer.md.j2'

# --- 输出文件名称常量 ---
FN_RAW_FETCHED = 'raw_fetched.jsonl'
FN_INGESTED = 'ingested.jsonl'
FN_FILTERED_RANKED = 'filtered_ranked.json'
FN_SUMMARY = 'summary.json'
FN_BRIEFING = 'briefing.md'

# ----------------------------------------------------------------------------

# === 通用配置字典 ===
class ConfigDict:
    """通用配置字典 — 递归将 dict 转为支持属性访问的对象"""

    def __init__(self, data: dict = None):
        data = data or {}
        for key, value in data.items():
            if isinstance(value, dict):
                value = ConfigDict(value)
            elif isinstance(value, list):
                value = [ConfigDict(item) if isinstance(item, dict) else item for item in value]
            object.__setattr__(self, key, value)

    def __repr__(self):
        return f"ConfigDict({self.__dict__})"


# ==================== 模块层配置 ====================
class ModuleLayerConfig:
    """模块层配置 - 各功能模块的业务参数"""

    def __init__(self, data: dict):
        # 数据源配置
        public_feeds = data.get('public_feeds', {})
        self.public_feeds = ConfigDict(public_feeds.get('settings', {}))
        self.public_feeds.feeds = public_feeds.get('feeds', [])
        
        # 去重配置
        self.dedup = ConfigDict(data.get('dedup', {}))
        
        # 筛选排序配置
        self.filter_rank = ConfigDict(data.get('filter_rank', {}))
        
        # 组装渲染配置
        self.assembly = ConfigDict(data.get('assembly', {}))


# ==================== 链接层配置 ====================
class LinkLayerConfig:
    """链接层配置 - 外部服务连接参数"""

    def __init__(self, data: dict):
        # LLM 客户端配置
        self.llm = ConfigDict(data.get('llm', {}))


# ==================== 协议层配置 ====================
class ProtocolLayerConfig:
    """协议层配置 - 数据交换协议与分类体系"""

    def __init__(self, data: dict):
        # 数据交换协议
        self.protocol = ConfigDict(data.get('protocol', {}))
        
        # 分类与标签配置
        self.classification = ConfigDict(data.get('classification', {}))
        
        # 标签白名单快捷访问
        tags_data = data.get('classification', {}).get('tags', {})
        self.vertical_tags_whitelist = tags_data.get('vertical_tags_whitelist', [])
        self.general_tags_whitelist = tags_data.get('general_tags_whitelist', [])


# ==================== 路径配置 ====================
class PathConfig:
    """路径配置 - 输出目录、模板文件等"""

    def __init__(self, date_str: str):
        self.date_str = date_str

    def output_dir(self) -> Path:
        """获取指定日期的输出目录"""
        return PROJECT_ROOT / 'output' / self.date_str

    def day_paths(self) -> dict:
        """获取指定日期的所有输出文件路径"""
        d = self.output_dir()
        return {
            'dir': d,
            'ingested': d / FN_INGESTED,
            'filtered': d / FN_FILTERED_RANKED,
            'summary': d / FN_SUMMARY,
            'briefing': d / FN_BRIEFING,
        }

    def get_templates_path(self) -> Path:
        """获取模板文件目录"""
        return CONFIG_DIR

    def get_prompts_path(self) -> Path:
        """获取提示词模板目录"""
        return PROMPTS_DIR


# ==================== 应用主配置 ====================
class AppConfig:
    """应用主配置 - 统一管理三层配置"""

    def __init__(self, date_str: str, config_path: str = None):
        self.date_str = date_str
        self.paths = PathConfig(date_str)
        
        self._config_path = config_path or str(CONFIG_YAML)
        raw = self._load_config()

        # ==================== 三层配置结构 ====================
        # 模块层 - 各功能模块业务参数
        self.modules = ModuleLayerConfig(raw)
        
        # 链接层 - 外部服务连接参数
        self.links = LinkLayerConfig(raw)
        
        # 协议层 - 数据交换协议与分类体系
        self.protocols = ProtocolLayerConfig(raw)
        
        self._load_secrets()

    def _load_config(self) -> dict:
        """加载 YAML 配置文件"""
        path = Path(self._config_path)
        if not path.is_file():
            raise FileNotFoundError(f'缺少配置文件: {path}')
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _load_secrets(self):
        """加载 secrets.json"""
        if not SECRETS_JSON.is_file():
            raise FileNotFoundError(f'缺少文件: {SECRETS_JSON}')
        import json
        with open(SECRETS_JSON, 'r', encoding='utf-8') as f:
            self._secrets = json.load(f)
        self._feishu_config = self._secrets.get('feishu', {})

    @property
    def feishu_config(self) -> dict:
        """获取飞书配置"""
        return self._feishu_config

    @property
    def llm_client_cfg(self) -> dict:
        """获取 LLM 客户端配置（合并 secrets 和 config）"""
        return {
            **self._secrets.get('llm', {}),
            'default_temperature': getattr(self.links.llm, 'default_temperature', 0.3),
            'default_max_tokens': getattr(self.links.llm, 'default_max_tokens', 2000),
        }
