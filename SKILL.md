---
name: ai-frontier-daily
description: >-
  每日 AI 前沿早报流水线：脚本产出 output/<日期>/agenda.md；Agent 负责编排执行与（按需）飞书发布。
  触发示例：「前沿早报」「每日 AI 早报」「刷新早报」、指定日期补跑、cron。
disable-model-invocation: true
---

# AI 前沿早报（Agent 执行手册）

本 Skill 描述 **Agent 与本仓库脚本如何配合**：脚本做确定性采集与生成；**早报正文不由 Chat 里当场撰写**，而是由 `summarize` 按提示词协议调用 LLM 后写入产物。**你的职责**主要是：在用户对应用触发时 **执行流水线 → 读取 `agenda.md` →（可选）按固定步骤发飞书 → 回传链接**。

---

## 1. 分工（必要性）

| 层级 | 做什么 | 不必做什么 |
|------|--------|------------|
| **脚本** | RSS → 粗筛 → 去重（含可选的近几日 `summary.json` 对照）→ LLM 摘要（协议校验、字段兜底）→ Jinja 渲染 `agenda.md` | — |
| **Agent** | `cd` 到仓库、运行编排命令、检查产物、读 Markdown、执行飞书 CLI | 不要用对话凭空重写一整份早报代替 `agenda.md` |

**原则：** 内容与结构以 **`output/<DATE>/agenda.md`** 为准；除非脚本失败且用户明确要求手工整理，否则不要绕过流水线杜撰终稿。

---

## 2. 一键执行（主路径）

在仓库根目录用虚拟环境 Python 调用编排入口（默认跑全天：`ingest` → `summarize` → `assemble`）。

| 变量 | 含义 |
|------|------|
| `SKILL_DIR` | 本Skill对应仓库根目录（示例：`/path/to/ai-frontier-daily`，请替换为你本机实际路径） |
| `DATE` | `YYYY-MM-DD`，默认当天 |

```bash
cd "$SKILL_DIR"
.venv/bin/python3 scripts/daily_ai_frontier.py --date "$DATE"
```

- **`--steps`**：默认 `all`。排错时可只跑部分，例如 `ingest`、`ingest,summarize`（逗号分隔）。

成功后终稿路径：

```text
$SKILL_DIR/output/$DATE/agenda.md
```

**Agent 发布前必须读取该文件**，不要用摘要代替全文去做飞书覆盖。

---

## 3. 分步执行（排错）

```bash
cd "$SKILL_DIR"
.venv/bin/python3 scripts/ingest.py       --date "$DATE"
.venv/bin/python3 scripts/summarize.py    --date "$DATE"
.venv/bin/python3 scripts/assemble.py     --date "$DATE"
```

`summarize` 依赖 `kit/config.json` 中的 LLM 配置；失败时先查密钥与网络，再重跑。

---

## 4. 产物说明（读什么）

| 文件 | 是否必读 | 说明 |
|------|----------|------|
| **`output/<DATE>/agenda.md`** | **是** | 对外发布的 Markdown 终稿 |
| `output/<DATE>/summary.json` | 一般否 | LLM 合并结果与 `blocks`；排错或抽检时用 |
| `output/<DATE>/ingested.jsonl` | 一般否 | 抓取与粗筛后的条目 |

---

## 5. 飞书发布（可选：用户需要「发到飞书」时）

下列命令与 **空间 ID / 节点 Token** 来自当前维护者环境；你若迁移到自己的知识库，请替换为自有常量。

### 5.1 推荐四步

| 顺序 | 动作 |
|------|------|
| 1 | `lark-cli docs +create --as user --doc-format markdown --content "# 占位"` → 得到文档 `TOKEN` |
| 2 | `lark-cli docs +update --as user --doc $TOKEN --mode overwrite --new-title "AI 前沿早报（$DATE）" --markdown - < agenda.md` |
| 3 | `lark-cli wiki +move --as user --obj-type docx --obj-token $TOKEN --target-space-id <空间ID> --target-parent-token <父节点TOKEN>` |
| 4 | 把文档/知识库可调链接返回给用户 |

### 5.2 参数常量（示例）

| 项 | 示例值 |
|----|--------|
| 文档标题 | `AI 前沿早报（YYYY-MM-DD）` |
| 账号模式 | `--as user`（勿用 Bot token 规避 wiki 移动权限问题） |

### 5.3 禁止

- 用 Bot token 建文档再移 wiki（易权限失败）。
- `docs +create` 时塞入整篇超长 Markdown（易排版异常）；应先占位再 `+update overwrite`。
- 发布后不按约定移入知识库（若流程要求归档）。

---

## 6. 异常速查

| 现象 | 建议 |
|------|------|
| 脚本非 0 退出 | 确认 `.venv` 存在、`pip` 依赖齐全；读 stderr |
| `ingested.jsonl` 为空 | 当日源站无命中或网络失败；告知用户「暂无采集结果」 |
| `summarize` 失败 | 检查 `kit/config.json`；修好后再跑 |
| 无 `agenda.md` | 按 §3 分步执行，看在哪一步中断 |

---

## 7. 配置与文档索引

| 需求 | 位置 |
|------|------|
| 来源 RSS、模块关键词、摘要字数、`dedup` | `kit/engineering.json` |
| LLM API | `kit/config.json`（通常不入库） |
| 字段协议、热点条数（8～12）、概要字数（尽量 ≤250 字） | `kit/prompts&templates/02_response_protocol.md`、`01_task.md` |
| 版面模板 | `kit/prompts&templates/agenda.md.j2` |
| 深度说明（管线扩展、历史约定） | [`reference.md`](reference.md) |
| `kit` 目录说明 | [`kit/README.md`](kit/README.md) |

---

## 8. 脚本职责一览

| 脚本 | 职责 |
|------|------|
| `daily_ai_frontier.py` | 解析 `--date` / `--steps`，按顺序调用各步 |
| `ingest.py` | 抓取、关键词粗筛、篇内去重、可选「近几日 summary」热点去重 |
| `summarize.py` | 注入提示词、解析 LLM JSON、校验与补全轮、字段兜底、`summary.json` |
| `assemble.py` | `summary.json` + 模板 → `agenda.md` |
| `base_config.py` | 路径与配置加载 |

---

## 9. LLM 输出协议（摘要）

`summarize` 期望根 JSON 包含 `deduplication`、`articles`、`blocks`。每条 `articles[]` 至少含：`point`、`one_liner`、`plain_explain`、`impact_1`、`impact_2`、`digest_for_outline`（**均为非空字符串**）；热点总量由模型按 **`drop_indices` 收敛在约 8～12 条（上限 12）**；`digest_for_outline` **尽量不超过约 250 字**，短稿勿灌水。

完整字段表与自检项以 **`02_response_protocol.md`** 为准；下方仅为结构示意：

```json
{
  "deduplication": { "drop_indices": [], "notes": "" },
  "articles": [
    {
      "source_index": 0,
      "point": "",
      "one_liner": "",
      "plain_explain": "",
      "impact_1": "",
      "impact_2": "",
      "digest_for_outline": ""
    }
  ],
  "blocks": {
    "header": { "tags_full": "", "data_sources": "" },
    "footer": {
      "hardware": "",
      "model": "",
      "ai_engineering": "",
      "industry": "",
      "policy": ""
    }
  }
}
```
