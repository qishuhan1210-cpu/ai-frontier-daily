# AI 前沿早报 — 参考手册（人类读者）

面向需要**改规则、查字段、扩配置**的贡献者。**日常跑链路**：先看 [`SKILL.md`](SKILL.md)。

---

## 目录

1. [仓库地图](#1-仓库地图)
2. [管线与产物](#2-管线与产物)
3. [project-space 目录与配置](#3-project-space-目录与配置)
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
| `project-space/pipeline.py` | 每日 AI 前沿早报编排入口：`--steps all` = ingest → summarize → assemble → 早报终稿 |
| `project-space/ingest.py` | 抓取 + 粗筛 + 去重，产出 `ingested.jsonl` |
| `project-space/summarize.py` | LLM 摘要，产出 `summary.json`（`items` + 可选 `blocks`） |
| `project-space/assemble.py` | 读 `summary.json`，组装上下文并渲染早报 Markdown |
| `project-space/utils/base_config.py` | 路径常量、`load_assembly_config`、`load_sources_config` 等配置加载器 |
| `project-space/utils/pipeline.py` | 规范步骤名 `ORDER` 与 `parse_steps` |
| `project-space/config/config.json` | 业务配置：RSS源、assembly模块、去重策略 |
| `project-space/config/briefing-template.md.j2` | 早报 Markdown 版式模板 |
| `project-space/prompts/summarizer.md.j2` | LLM 摘要生成提示词（含响应协议） |
| `config/.env` | 敏感信息：API Key、Webhook URL（gitignored） |
| `output/{date}/` | 当日产物目录（见 §2） |

---

## 2. 管线与产物

单日目录 `output/{YYYY-MM-DD}/` 仅保留**三个核心文件**（中间步骤不落盘）：

| 阶段 | 产物 | 说明 |
|------|------|------|
| ingest | `ingested.jsonl` | RSS → 关键词粗筛 → 去重后的条目（JSONL） |
| summarize | `summary.json` | `{"items":[...], "blocks": {...}}`；无 blocks 时为 `null` |
| assemble | 早报 Markdown 文件 | Jinja 渲染终稿（默认交付物） |

可选：`summarize.py` 仍接受**任意 JSONL** 作为 `-i` 输入（例如手工精筛后的文件），需在命令行显式指定路径。自行维护 `04_validated.jsonl` 等命名时，行格式见 §7。

---

## 3. project-space 目录与配置

- **`project-space/config/config.json`**：业务配置，含 `sources`（tier1/excluded）、`assembly`（模块列表、头图覆盖文案）、`dedup`（去重策略）、`public_feeds`（RSS源）。改版面模块或来源策略时改此文件。
- **`project-space/config/briefing-template.md.j2`**：早报 Markdown 渲染模板。
- **`project-space/prompts/summarizer.md.j2`**：LLM 摘要生成提示词，内含响应协议定义。
- **`config/.env`**：敏感信息（API Key、Webhook URL），已 gitignore，首次配置时创建。

---

## 4. LLM：提示词与 Jinja

### 4.1 核心提示词文件

| 文件 | 职责 |
|------|------|
| `project-space/prompts/summarizer.md.j2` | 完整提示词：System 角色定义 + User 事项描述 + 响应协议 + 运行时注入 |

### 4.2 Jinja2 模板（`autoescape` 关）

| 文件 | 职责 |
|------|------|
| `project-space/config/briefing-template.md.j2` | 早报 Markdown 版式模板 |

运行时：`summarize.py` 加载 `summarizer.md.j2`，注入当日新闻数据后调用 LLM；`assemble.py` 使用 `briefing-template.md.j2` 渲染最终早报。

### 4.3 模版变量提示

早报模版中列表变量用 `section.entries` / `unknown.entries`，**勿用** `items`（与 Jinja 内建冲突）。

---

## 5. 条目字段与编辑总则

与统一管线中 `articles[]` 及 `assemble.py` + `briefing-template.md.j2` 一致；**配置以 `project-space/config/config.json` 的 `sources` / `assembly` 为准**。

### 5.1 六字段与下游映射

| 呈现字段 | 摘要 JSON | 说明 |
|----------|-----------|------|
| 标题 | `headline` | 融合从业者视角 + 客观事件概括，40-50字 |
| 标签 | `tag` | 从六类标签中选1个（见 §5.3 标签体系） |
| 概要 | `digest_for_outline` | 信息丰富的摘要，含主体/时间/数字/结论，≤250字 |
| 🌱 白话解释 | `plain_explain` | 面向小白，解释企业角色和生僻概念 |
| 🎯 影响 | `impact_1` / `impact_2` | 两个具体影响点，单行内联展示 |

### 5.2 规则摘要

- **条**：标题 40-50 字，融合价值点与客观概括；链接须指向**正文页**（策略见 `config.json` → `sources`）；概要约 200–250 字，必须含时间/数字/结论；白话约 50-80 字，解释企业角色和概念；影响 2 点、具体。
- **风格**：简洁、具体（数字/公司全名）、中立。
- **禁止**：标题异常标记；一对多链、首页/频道/聚合；空泛口语；凑字数灌水。
- **组装后 Markdown**：模块内 `1.1` `1.2` `1.3` …；条末 `---`。
- **来源**：以 `sources.tier1` / `excluded` 为权威参考。

### 5.3 标签体系

每条新闻必须打一个标签，从以下六类中选择：

| 标签 | 定义 | 适用场景 |
|------|------|----------|
| **企业/用户硬件** | AI 相关硬件设备 | GPU/AI芯片、AI手机、AI PC、智能穿戴、边缘计算设备 |
| **协议/基建** | AI 基础设施与通信协议 | MCP、A2A、API标准、数据中心、算力集群、云基础设施 |
| **AI落地与协作** | AI 应用落地与人机协作 | AI编程工具、Agent工作流、企业AI应用、人机交互 |
| **地缘政治** | 国家间 AI 竞争与监管 | **仅限**：出口管制、芯片封锁、国家AI战略、跨国监管；**不包括**：企业间竞争 |
| **模型技术** | 大模型技术进展 | 模型发布、能力评测、多模态、参数/架构创新、训练方法 |
| **产业商业** | AI 产业动态与商业 | 融资并购、商业化落地、科技巨头财报、AI企业战略合作 |

**选题纠偏原则**：
- **保留**：AI 前沿技术、AI 落地应用、人机协作关系
- **剔除**：纯硬件（无 AI 关联）、纯金融基金、纯消费娱乐、纯汽车（非智驾相关）

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

仅在**自行增加「人工精筛」步骤**时使用。每行一条 JSON，`module` 须与 `config.json` → `assembly.modules` 五大板块一致：

```json
{"id":"","title":"","url":"","source":"","pub_time":"","headline":"","module":"hardware|model|ai_engineering|industry|policy","relevant":true}
```

`relevant: false` 的条目不应进入摘要。若使用该文件作为 `summarize.py` 输入，在命令行显式传入路径即可。

**注意**：已用 `headline` 替代旧字段 `point`，格式为 `1.1` `1.2` 而非 `a` `b` `c`。

---

## 8. 交付范围

- **默认交付物**：`output/{date}/` 目录下的早报 Markdown 文件。

---

## 9. 异常与兜底

- **爬取失败**：可人工补源或改 RSS；规则见 `engineering.json`。
- **排除源 / 坏链**：按 `sources` 与链接策略替换或剔除。
- **某模块无稿**：组装侧可保留章节标题，正文用占位句（实现以 `assemble.py` / 模版为准）。
- **API 失败**：保留已有 `summary.json` 和早报文件，修复密钥后重跑 `summarize` 或 `daily_ai_frontier`。
