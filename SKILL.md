---
name: ai-frontier-daily
description: >-
  编排 AI 前沿早报脚本链路：ingest（抓取·过滤·去重）→ summarize → assemble，产出当日 `agenda.md`。在用户提及 AI 前沿早报、每日早报、`daily_ai_frontier`、前沿日报或显式引用本 skill 时使用。
disable-model-invocation: true
---

# AI 前沿早报

下文给出**可执行的 bash 步骤**。字段规则、`blocks`、管线扩展：**人类读者**请读 [`reference.md`](reference.md)；勿在 `SKILL.md` 内重复长规则。`kit` 目录索引见 [`kit/README.md`](kit/README.md)。

---

## 架构

```
Agent
  → scripts/daily_ai_frontier.py --date YYYY-MM-DD   （--steps all）
      ingest → summarize → assemble → output/{date}/agenda.md
```

单日目录仅三个核心文件：`ingested.jsonl` → `summary.json` → `agenda.md`。

---

## 工作流

**`SKILL_DIR`** = 本 skill 根目录。进入该目录执行；`output/{date}/` 由脚本创建。

### Step 1 — ingest（抓取 · 粗筛 · 去重）

```bash
cd "$SKILL_DIR"
.venv/bin/python3 scripts/ingest.py --date "$TODAY"
# 默认写出 output/$TODAY/ingested.jsonl
```

### Step 2 — summarize（LLM）

```bash
.venv/bin/python3 scripts/summarize.py --date "$TODAY"
# 默认读 ingested.jsonl，写 summary.json（含 items + 可选 blocks）
```

### Step 3 — assemble（终产物 `agenda.md`）

```bash
.venv/bin/python3 scripts/assemble.py --date "$TODAY"
# 默认读 summary.json，写 agenda.md
```

模块与头图覆盖文案来自 `kit/engineering.json` 中的 `assembly`；条目与 `blocks` 见 [`reference.md`](reference.md)。

**一键**

```bash
cd "$SKILL_DIR"
.venv/bin/python3 scripts/daily_ai_frontier.py --date "$TODAY"
```

---

## Machine routing（LLM）

以下用于**定位脚本与路径**；细则见 [`reference.md`](reference.md)。

- **`daily_ai_frontier`**：`scripts/daily_ai_frontier.py` — 每日 AI 前沿早报编排入口；`--date`，`--steps` 或 `all`。`all` ≡ `ingest,summarize,assemble` → `output/{date}/agenda.md`；未知步骤名会告警。
- **`ingest`**：`scripts/ingest.py` — `run_ingest`；默认 `-o output/<date>/ingested.jsonl`。
- **`summarize`**：`scripts/summarize.py` — `run_summarize`；默认 `-i` ingested、`-o` summary.json；根路径 `base_config.TEMPLATES_DIR`。
- **`assemble`**：`scripts/assemble.py` — `run_assemble`；读 summary、构建上下文并以模版 `agenda.md.j2` 写出终稿。
- **`pipeline`**：`scripts/pipeline.py` — 规范步骤名 `ORDER`、`parse_steps`。
- **`base_config`**：`scripts/base_config.py` — 路径、`default_day_paths`、`engineering.json` 与 `config.json` 相关常量及加载函数。
- **`scripts` 包**：`from scripts import …` 见 `scripts/__init__.py` 再导出（与分模块 `import` 等价）。

Artifact chain：`ingested.jsonl` → `summary.json` → `agenda.md`。
