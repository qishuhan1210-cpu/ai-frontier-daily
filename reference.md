# AI 前沿早报 — 参考手册（人类读者）

面向需要**改规则、查字段、扩配置**的贡献者。**日常跑链路**：先看 [`SKILL.md`](SKILL.md)。

---

## 目录

1. [仓库地图](#1-仓库地图)
2. [管线与产物](#2-管线与产物)
3. [kit 目录与配置](#3-kit-目录与配置)
4. [LLM：提示词与 Jinja](#4-llm提示词与-jinja)
5. [条目字段与编辑总则](#5-条目字段与编辑总则)
6. [blocks 与组装](#6-blocks-与组装)
7. [可选：04_validated.jsonl](#7-可选04_validatedjsonl)
8. [交付范围](#8-交付范围)
9. [异常与兜底](#9-异常与兜底)

---

## 1. 仓库地图

| 路径 | 职责 |
|------|------|
| `scripts/daily_ai_frontier.py` | 每日 AI 前沿早报编排入口：`--steps all` = ingest → summarize → assemble → `agenda.md` |
| `scripts/__init__.py` | 包级再导出（`ORDER`、`default_day_paths`、`load_*` 等），实现仍在 `base_config` / `pipeline` |
| `scripts/pipeline.py` | 规范步骤名 `ORDER` 与 `parse_steps`（解析 `--steps`，未知片段告警） |
| `scripts/ingest.py` | 抓取 + 粗筛 + 去重，产出 `ingested.jsonl`（`run_ingest`） |
| `scripts/summarize.py` | LLM 摘要，产出 `summary.json`（`items` + 可选 `blocks`）；`run_summarize` |
| `scripts/assemble.py` | 读 `summary.json`，组装上下文并渲染 `agenda.md`（`run_assemble`） |
| `scripts/base_config.py` | 路径常量、`default_day_paths`、`FN_*`；`load_assembly_config`、`load_sources_config`、`load_public_feeds_config`、`load_dedup_config` 等（读 `engineering.json`） |
| `kit/engineering.json` | 来源、tier、assembly 模块、去重等工程规则 |
| `kit/prompts&templates/` | `01_task.md`、`02_response_protocol.md`、`agenda.md.j2`、`system.md.j2`、`runtime_injection.md.j2` |
| `kit/config.json` | API 密钥等（示例：`config.example.json`） |
| `output/{date}/` | 当日产物目录（见 §2） |

---

## 2. 管线与产物

单日目录 `output/{YYYY-MM-DD}/` 仅保留**三个核心文件**（中间步骤不落盘）：

| 阶段 | 产物 | 说明 |
|------|------|------|
| ingest | `ingested.jsonl` | RSS → 关键词粗筛 → 去重后的条目（JSONL） |
| summarize | `summary.json` | `{"items":[...], "blocks": {...}}`；无 blocks 时为 `null` |
| assemble | `agenda.md` | Jinja 渲染终稿（默认交付物） |

可选：`summarize.py` 仍接受**任意 JSONL** 作为 `-i` 输入（例如手工精筛后的文件），需在命令行显式指定路径。自行维护 `04_validated.jsonl` 等命名时，行格式见 §7。

---

## 3. kit 目录与配置

- **`engineering.json`**：`sources`（含 tier / 排除）、`assembly`（模块列表、头图覆盖文案、`summary_unified_*` 等）、去重相关键。改版面模块或来源策略时改此文件。
- **`config.json`**：LLM API 等密钥（不入版本库时用本地文件）。
- **索引**：见 [`kit/README.md`](kit/README.md)（目录内各 `.md` / `.j2` 的职责说明）。

---

## 4. LLM：提示词与 Jinja

### 4.1 由代码加载的 Markdown（User 正文组成部分）

| 文件 | 职责 |
|------|------|
| `kit/prompts&templates/01_task.md` | 事项描述：角色与任务边界 |
| `kit/prompts&templates/02_response_protocol.md` | 根 JSON 结构与字段约束 |

### 4.2 Jinja2（`autoescape` 关）

| 文件 | 职责 |
|------|------|
| `kit/prompts&templates/system.md.j2` | System 消息（`summarize.build_system_prompt`） |
| `kit/prompts&templates/runtime_injection.md.j2` | User 末尾运行时注入 |
| `kit/prompts&templates/agenda.md.j2` | 早报 `agenda.md` 版式 |

运行时：`summarize.py` 将 §4.1 + 注入段拼成 User；System / 注入模版由 `base_config.TEMPLATES_DIR` 加载。

### 4.3 模版变量提示

早报模版中列表变量用 `section.entries` / `unknown.entries`，**勿用** `items`（与 Jinja 内建冲突）。

---

## 5. 条目字段与编辑总则

与统一管线中 `articles[]` 及 `assemble.py` + `agenda.md.j2` 一致；**配置以 `engineering.json` 的 `sources` / `assembly` 为准**。

### 5.1 六字段与下游映射

| 呈现字段 | 摘要 JSON |
|----------|-----------|
| Point | `point` |
| 一句话 | `one_liner` |
| 概要 | 长摘要正文或 `_ai_summary` |
| 🌱 白话解释 | `plain_explain` |
| 🎯 影响 | `impact_1` / `impact_2` |

### 5.2 规则摘要

- **条**：Point 一句、从业者可读；一句话约 25 字、客观；链接须指向**正文页**（策略见 `engineering.json` → `sources`）；概要约 200–300 字；白话约 50 字；影响 2–4 点、具体。
- **风格**：简洁、具体（数字/公司全名）、中立。
- **禁止**：标题异常标记；一对多链、首页/频道/聚合；空泛口语。
- **组装后 Markdown**：模块内 `a.` `b.` `c.` …；条末 `---`。
- **来源**：以 `sources.tier1` / `excluded` 为权威参考。

---

## 6. blocks 与组装

由 `summarize.py` 写入 `summary.json` 的 `blocks` 字段；`assemble.py` 拼入早报头尾。

**原则**：LLM 只填结构化字段；工程用头部模版、`build_footer()` 等与正文拼接。

**形态示例**（与根响应 `blocks` 一致）：

```json
{
  "header": {
    "tags_full": "#AI早报 #标签…",
    "data_sources": "来源A · 来源B"
  },
  "footer": {
    "hardware": "…",
    "model": "…",
    "ai_engineering": "…",
    "industry": "…",
    "policy": "…"
  }
}
```

| 协议路径 | 工程用途 |
|----------|----------|
| `header.tags_full` | 头部「标签」行 |
| `header.data_sources` | 头部「数据来源」行 |
| `footer.<module_id>` | 速览一行；键名同 `assembly.modules[].id` |

---

## 7. 可选：04_validated.jsonl

仅在**自行增加「人工精筛」步骤**时使用。每行一条 JSON，`module` 须与 `engineering.json` → `assembly.modules` 五大板块一致：

```json
{"id":"","title":"","url":"","source":"","pub_time":"","point":"","module":"硬件·芯片|模型|AI工程·Agent|产业·商业|政策·地缘","relevant":true}
```

`relevant: false` 的条目不应进入摘要。若使用该文件作为 `summarize.py` 输入，在命令行显式传入路径即可。

---

## 8. 交付范围

- **默认交付物**：`output/{date}/agenda.md`。

---

## 9. 异常与兜底

- **爬取失败**：可人工补源或改 RSS；规则见 `engineering.json`。
- **排除源 / 坏链**：按 `sources` 与链接策略替换或剔除。
- **某模块无稿**：组装侧可保留章节标题，正文用占位句（实现以 `assemble.py` / 模版为准）。
- **API 失败**：保留已有 `summary.json` / `agenda.md`，修复密钥后重跑 `summarize` 或 `daily_ai_frontier`。
