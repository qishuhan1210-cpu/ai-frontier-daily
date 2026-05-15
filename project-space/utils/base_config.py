#!/usr/bin/env python3
"""base_config.py — 统一配置管理"""

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


# === 应用主配置 ===
class AppConfig:
    """应用主配置"""

    def __init__(self, config_path: str = None):
        self._config_path = config_path or str(CONFIG_YAML)
        raw = self._load_config()

        public_feeds = raw.get('public_feeds', {})
        self.feeds = ConfigDict(public_feeds.get('settings', {}))
        self.feeds.feeds = public_feeds.get('feeds', [])

        self.dedup = ConfigDict(raw.get('dedup', {}))
        self.llm = ConfigDict(raw.get('llm', {}))
        self.filter_rank = ConfigDict(raw.get('filter_rank', {}))
        self.assembly = ConfigDict(raw.get('assembly', {}))

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
            secrets = json.load(f)
        self._secrets = secrets
        self._feishu_config = secrets.get('feishu', {})
        self._llm_client_cfg = {
            **secrets.get('llm', {}),
            'default_temperature': getattr(self.llm, 'default_temperature', 0.3),
            'default_max_tokens': getattr(self.llm, 'default_max_tokens', 2000),
        }

    @property
    def llm_client_cfg(self) -> dict:
        """获取 LLM 客户端配置（合并 secrets 和 config）"""
        return self._llm_client_cfg

    @property
    def header_coverage(self) -> str:
        """动态生成 header_coverage"""
        modules = self.assembly.modules
        return ' · '.join(m.name for m in modules)

    def output_dir(self, date_str: str) -> Path:
        """获取指定日期的输出目录"""
        return PROJECT_ROOT / 'output' / date_str

    def day_paths(self, date_str: str) -> dict:
        """获取指定日期的所有输出文件路径"""
        d = self.output_dir(date_str)
        return {
            'dir': d,
            'ingested': d / FN_INGESTED,
            'filtered': d / FN_FILTERED_RANKED,
            'summary': d / FN_SUMMARY,
            'briefing': d / FN_BRIEFING,
        }

    def get_templates_path(self) -> Path:
        return CONFIG_DIR

    def get_prompts_path(self) -> Path:
        return PROMPTS_DIR