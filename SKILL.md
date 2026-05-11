---
name: ai-frontier-daily
description: >-
  每日 AI 前沿早报流水线：自动采集 RSS → LLM 摘要 → 渲染早报 Markdown → 飞书发布 + 群机器人 Webhook。
  这是一个定时任务 Skill，通过 cron 自动执行，无需用户主动触发。
disable-model-invocation: true
---

# AI 前沿早报（定时任务执行手册）

本 Skill 为**定时自动化流水线**，默认通过 cron 每日自动执行。**Agent 仅在异常或补跑时介入**。

| 层级 | 职责 | 产物 |
|------|------|------|
| **脚本** | RSS 采集 → 去重 → LLM 摘要 → Jinja 渲染 | `output/<DATE>/` 目录下的早报 Markdown |
| **Agent** | 异常排查、指定日期补跑、发布流程编排 | 飞书文档 + 群推送 |

---

## 1. 何时启用 / 何时不用

| 场景 | 处理方式 |
|------|----------|
| **每日定时运行** | 不需要 Agent 介入，cron 自动执行 |
| **异常排查** | 日志显示失败，需 Agent 介入检查 |
| **指定日期补跑** | 用户说「重跑5月9日」，Agent 介入执行 |
| **手动撰写早报** | ❌ 不支持，内容由脚本生成 |
| **非 AI 类新闻汇总** | ❌ 不支持，本流水线仅处理 AI 前沿 |

---

## 2. 执行命令

### 2.1 一键执行（正常流程）

```bash
cd /Users/huangxingbiao/.qclaw/skills/ai-frontier-daily
python3 project-space/pipeline.py --date "YYYY-MM-DD"
```

- 默认执行全部步骤：`ingest` → `summarize` → `assemble`
- 产物路径：`output/<DATE>/` 目录下的早报 Markdown 文件

### 2.2 分步执行（排错）

```bash
cd /Users/huangxingbiao/.qclaw/skills/ai-frontier-daily
python3 project-space/ingest.py --date "YYYY-MM-DD"
python3 project-space/summarize.py --date "YYYY-MM-DD"
python3 project-space/assemble.py --date "YYYY-MM-DD"
```

### 2.3 补跑历史日期

```bash
# 例如重跑 5 月 9 日
python3 project-space/pipeline.py --date "2026-05-09"
```

---

## 3. 产物说明

| 文件 | 职责 | 必读 |
|------|------|------|
| `output/<DATE>/` 目录下的早报 Markdown | 对外发布的终稿 | ✅ 是 |
| `output/<DATE>/summary.json` | LLM 合并结果，用于飞书机器人推送 | 发布时需要 |
| `output/<DATE>/ingested.jsonl` | 原始采集条目，排错时用 | 否 |

---

## 4. 发布后流程（早报终稿生成后）

脚本成功后，按以下步骤执行：

| 步骤 | 动作 | 文档 |
|------|------|------|
| 1 | 读取终稿确认内容 | `output/<DATE>/` 目录下的早报 Markdown 文件 |
| 2 | 发布到飞书知识库 | 见 `extension/post-runbook.md` §2 |
| 3 | 群机器人 Webhook 推送 | 见 `extension/post-runbook.md` §4 |
| 4 | 返回文档链接给用户 | — |

---

## 5. 配置说明

所有配置分为两类：

| 配置类型 | 位置 | 是否可提交 Git |
|----------|------|----------------|
| **业务配置**（RSS 源、模块、去重策略等） | `project-space/config/config.json` | ✅ 是 |
| **敏感信息**（API Key、Webhook） | `.env` | ❌ 否（已 gitignore） |
| **发布目标**（知识库 space_id、parent_token） | 对话上下文 | 由大模型自行判断 |

### 5.1 首次配置

1. **复制环境变量模板**：
   ```bash
   cp .env.example .env
   ```

2. **编辑 `.env`**，填入你的真实值：
   ```bash
   # LLM API 配置
   LLM_API_KEY=sk-your-real-api-key
   LLM_BASE_URL=https://api.deepseek.com
   LLM_MODEL_NAME=deepseek-chat

   # 飞书机器人 Webhook
   FEISHU_BOT_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/your-token
   ```

   **注意**：飞书知识库发布目标（`space_id`、`parent_node_token`）不在 `.env` 中配置，由大模型根据对话上下文自行判断。详见 `extension/post-runbook.md`。

3. **安装依赖**（如果尚未安装）：
   ```bash
   pip install python-dotenv
   ```

### 5.2 配置索引

| 需求 | 位置 |
|------|------|
| 发布后流程（含 Webhook、知识库发布） | `extension/post-runbook.md` |
| RSS 来源、模块、去重策略 | `project-space/config/config.json` |
| LLM API（Key/BaseUrl/Model）| `.env`（从环境变量读取） |
| Webhook | `.env`（从环境变量读取） |
| 知识库发布目标 | 大模型根据对话上下文自行判断 |
| 提示词模板 | `project-space/prompts/summarizer.md.j2` |
| 早报模板 | `project-space/config/briefing-template.md.j2` |

---

## 6. 异常速查

| 现象 | 建议 |
|------|------|
| 脚本非 0 退出 | 检查虚拟环境、依赖完整性；查看 stderr |
| `ingested.jsonl` 为空 | 当日源站无命中或网络失败；告知用户「暂无采集结果」 |
| `summarize` 失败 | 检查 `.env` 中的 `LLM_API_KEY`；修复后重跑 |
| 无早报文件 | 按 §2.2 分步执行，定位中断步骤 |
| 飞书发布失败 | 确认大模型已正确识别目标知识库（space_id、parent_node_token）|
| Webhook 推送失败 | 检查 `.env` 中的 `FEISHU_BOT_WEBHOOK` |

---

## 7. 安全与敏感信息

| 环境变量 | 用途 | 所在文件 |
|----------|------|----------|
| `LLM_API_KEY` | LLM API 认证 | `.env`（gitignore） |
| `FEISHU_BOT_WEBHOOK` | 飞书群机器人推送 | `.env`（gitignore） |
| 知识库 `space_id` / `parent_node_token` | 飞书知识库发布目标 | 大模型根据对话上下文自行判断 |

**注意**：`.env.example` 是模板文件（可提交），`.env` 是真实配置（已 gitignore）。

