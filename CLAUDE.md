# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

每日 AI 前沿早报自动化流水线：RSS 采集 → LLM 筛选/摘要 → 多平台渲染 → 飞书发布。

## 环境初始化

```bash
# 首次使用
./scripts/base/init_env.sh
cp config/secrets.example.json config/secrets.json
# 编辑 config/secrets.json 填入实际配置
```

## 常用命令

```bash
# 运行完整流水线（推荐通过 Lobster 工具执行）
./scripts/base/run.sh python scripts/news_frontier.py --date 2026-06-18

# 只执行指定步骤
./scripts/base/run.sh python scripts/news_frontier.py --steps ingest
./scripts/base/run.sh python scripts/news_frontier.py --steps filter_rank,summarize

# 运行所有测试
pytest

# 运行单个测试文件
pytest project-space/tests/test_llm_client.py -v

# 运行单个测试函数
pytest project-space/tests/test_llm_client.py::TestLLMClient::test_call -v
```

> **重要**：正式工作流必须用 Lobster 工具执行（`references/ai-frontier-daily.lobster`，timeoutMs >= 300000），不可直接调用脚本。

## 架构概览

### 核心流水线（4 个串行阶段）

`scripts/news_frontier.py` 编排以下模块，均位于 `project-space/`（已加入 `sys.path`）：

| 阶段 | 模块 | 输入 → 输出 |
|------|------|-------------|
| `ingest` | `IngestModule` | RSS 源 → `output/{DATE}/ingested.jsonl` |
| `filter_rank` | `FilterRankModule` | `ingested.jsonl` → `filtered_ranked.json` |
| `summarize` | `SummarizeModule` | `filtered_ranked.json` → `summary.json` |
| `assemble` | `AssembleModule` | `summary.json` → 多平台 Markdown/HTML |

### 三层配置架构（`project-space/utils/base_config.py`）

`AppConfig` 统一管理所有配置，按关注点分层：

- `config.modules`（ModuleLayerConfig）：feeds、dedup、filter_rank、keyword_dedup、assembly 等业务参数
- `config.links`（LinkLayerConfig）：LLM API 调用参数
- `config.protocols`（ProtocolLayerConfig）：数据字段协议 + 分类/标签体系

业务参数来自 `project-space/config/config.yaml`（可提交），密钥来自 `config/secrets.json`（gitignore）。

### LLM 客户端（`project-space/utils/llm_client.py`）

支持 OpenAI（默认）和 Claude 两种后端，通过 `secrets.json` 中 `llm.model_type` 切换（`"openai"` 或 `"claude"`）。核心方法：`call(system, user)` 返回文本，`call_json(system, user)` 自动解析 JSON。

### 分发链路（按需启用，由 Lobster 配置决定）

`scripts/` 下的分发脚本独立运行：
- `publish2lark.py`：发布到飞书知识库（按月归档、同名去重）
- `push2group.py`：推送飞书群交互式卡片（依赖 `publish2lark` 输出的文档 URL）
- `publish2lark_base.py`：写入飞书多维表格
- `render_wechat.sh`：微信公众号 HTML 渲染
- `screenshot-redbook.js`：小红书卡片批量截图

### 关键路径

- 配置加载：`AppConfig.__init__` 同时加载 `config.yaml` 和 `secrets.json`
- Prompt 模板：`project-space/prompts/` 下 `.j2.md` 文件，通过 `utils/prompt_loader.py` 加载
- 渲染模板：`project-space/config/` 下 `.j2` 文件（飞书 Markdown、微信 HTML、小红书 HTML）
- 日志：`utils/logger.py`，按日期写入 `project-space/logs/`