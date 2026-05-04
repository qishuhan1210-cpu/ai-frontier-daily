---

## name: ai-frontier-daily
description: >-
  每日 AI 前沿早报流水线：脚本产出 output/<日期>/agenda.md；Agent 负责编排执行；agenda 生成后的飞书发布、必做 Webhook 与回传见 post-runbook.md（可由 post-runbook.example.md 复制）。
  触发示例：「前沿早报」「每日 AI 早报」「刷新早报」、指定日期补跑、cron。
disable-model-invocation: true

# AI 前沿早报（Agent 执行手册）

本 Skill 描述 **Agent 与本仓库脚本如何配合**：脚本做确定性采集与生成；**早报正文不由 Chat 里当场撰写**，而是由 `summarize` 按提示词协议调用 LLM 后写入产物。**你的职责**主要是：在用户对应用触发时 **执行流水线**；当 `**agenda.md` 已成功生成** 后，再按 `**[post-runbook.md](post-runbook.md)`**（若无则从 `**[post-runbook.example.md](post-runbook.example.md)**` 复制并本地化）做发布前阅读、飞书发布、**必做的** Webhook 推送与用户回传。

---

## 1. 分工（必要性）


| 层级        | 做什么                                                                                                                           | 不必做什么                        |
| --------- | ----------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| **脚本**    | RSS → 粗筛 → 篇内去重 → **与近 N 日已产出 `summary.json` 对照剔除重复热点**（默认 N=7，见 `engineering.json` → `dedup`）→ LLM 摘要 → Jinja 渲染 `agenda.md` | —                            |
| **Agent** | `cd` 到仓库、运行编排命令、检查产物；`agenda.md` 产出后按 `**[post-runbook.md](post-runbook.md)`** 读终稿、飞书发布与 Webhook、回传链接                         | 不要用对话凭空重写一整份早报代替 `agenda.md` |


**原则：** 内容与结构以 `**output/<DATE>/agenda.md`** 为准；除非脚本失败且用户明确要求手工整理，否则不要绕过流水线杜撰终稿。

---

## 2. 一键执行（主路径）

在仓库根目录用虚拟环境 Python 调用编排入口（默认跑全天：`ingest` → `summarize` → `assemble`）。


| 变量          | 含义                                                         |
| ----------- | ---------------------------------------------------------- |
| `SKILL_DIR` | 本Skill对应仓库根目录（示例：`/path/to/ai-frontier-daily`，请替换为你本机实际路径） |
| `DATE`      | `YYYY-MM-DD`，默认当天                                          |


```bash
cd "$SKILL_DIR"
.venv/bin/python3 scripts/daily_ai_frontier.py --date "$DATE"
```

- `**--steps**`：默认 `all`。排错时可只跑部分，例如 `ingest`、`ingest,summarize`（逗号分隔）。

成功后终稿路径：

```text
$SKILL_DIR/output/$DATE/agenda.md
```

成功产出后的具体操作（必读终稿、飞书、回传链接）见 `**[post-runbook.md](post-runbook.md)**`；本文件 **§5** 为同主题入口表。仓库内可入库的模板为 `**[post-runbook.example.md](post-runbook.example.md)`**。

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


| 文件                             | 是否必读  | 说明                         |
| ------------------------------ | ----- | -------------------------- |
| `**output/<DATE>/agenda.md**`  | **是** | 对外发布的 Markdown 终稿          |
| `output/<DATE>/summary.json`   | 一般否   | LLM 合并结果与 `blocks`；排错或抽检时用 |
| `output/<DATE>/ingested.jsonl` | 一般否   | 抓取与粗筛后的条目                  |


### ingest：与近 7 日已产出热点的去重（filter）

`ingest.py` 在 **篇内去重之后**，会读取 **ingest 日当天之前、连续 N 个日历日** 的 `output/<YYYY-MM-DD>/summary.json`（文件存在才载入），为其中 `items` 构造指纹，并与当日 RSS 条目比对：**URL 归一化一致**，或 **标题** / **正文** n-gram Jaccard 超过阈值则视为重复热点并 **剔除**，避免连续多日推送同一题材。

- **N（对照窗口）**：`kit/engineering.json` → `**dedup.recent_summary_days`**（默认 **7**）。与 **§5「`output/` 历史清理」** 保留近 7 天搭配时，本地仍会保留用于对照的 `summary.json`。
- **关闭**：`dedup.recent_summary_enabled` 设为 `false`。
- **调参**：`recent_summary_title_threshold`、`recent_summary_text_threshold` 与同文件 `dedup` 下篇内去重共用 `word_ngram_n` / `char_ngram_n`。

---

## 5. Post-agenda runbook（`agenda.md` 已生成后）

流水线已成功写出 `**output/<DATE>/agenda.md`** 时，从这里继续：


| 内容                                            | 文档                                                       |
| --------------------------------------------- | -------------------------------------------------------- |
| 发布前读终稿、飞书四步、**必做 Webhook**、回传链接（个人环境专用，默认不入库） | `**[post-runbook.md](post-runbook.md)`**                 |
| 可复制入库的模板与 Case 说明（无个人命令细节）                    | `**[post-runbook.example.md](post-runbook.example.md)**` |
| `output/` 历史目录滚动保留 **近 7 天**（维护磁盘；主流程完成后再做）   | 本节 **「`output/` 历史清理」** 小节                               |


不要在未读终稿的情况下用摘要覆盖飞书；不要绕过流水线杜撰终稿（例外见 **runbook** 与 `SKILL.md` 的约定）。

**首次使用：** 将 `post-runbook.example.md` 复制为 `post-runbook.md` 后按本机补充。`post-runbook.md` 已列入 `**.gitignore`**（与 `config.json` 类似，勿提交个人步骤）。

### `output/` 历史清理（保留近 7 天）

在当日 `**agenda.md` 已成功产出**且发布/Webhook/回传等 **§5 主流程无阻塞** 后，可对 `**output/`** 做滚动清理：`output/YYYY-MM-DD` 仅保留 **含当日在内连续 7 个自然日** 对应的目录，删除更早的日期目录，避免长期跑流水线占满磁盘。**删除前**确认无本地任务仍依赖被删日期的产物。

- **约定：** 子目录名须为 `YYYY-MM-DD`（与流水线一致）；仅处理该形态，勿误删其它路径。
- **macOS：**

```bash
cd "$SKILL_DIR"
keep_from=$(date -v-6d +%Y-%m-%d)
for d in output/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]; do
  [ -d "$d" ] || continue
  b=$(basename "$d")
  [[ "$b" < "$keep_from" ]] && rm -rf "$d"
done
```

- **GNU/Linux（`date`）：** 将 `keep_from=$(date -v-6d +%Y-%m-%d)` 换为 `keep_from=$(date -d '-6 days' +%Y-%m-%d)`（或与你发行版一致的等价写法）。

---

## 6. 异常速查


| 现象                  | 建议                                |
| ------------------- | --------------------------------- |
| 脚本非 0 退出            | 确认 `.venv` 存在、`pip` 依赖齐全；读 stderr |
| `ingested.jsonl` 为空 | 当日源站无命中或网络失败；告知用户「暂无采集结果」         |
| `summarize` 失败      | 检查 `kit/config.json`；修好后再跑        |
| 无 `agenda.md`       | 按 §3 分步执行，看在哪一步中断                 |


---

## 7. 配置与文档索引


| 需求                                               | 位置                                                           |
| ------------------------------------------------ | ------------------------------------------------------------ |
| **agenda 生成后的发布与回传（工作副本，git 忽略）**                | `[post-runbook.md](post-runbook.md)`                         |
| **同上（可入库模板 + Case 说明）**                          | `[post-runbook.example.md](post-runbook.example.md)`         |
| **飞书群 Webhook**（必做；`scripts/push_feishu_bot.py`） | `[post-runbook.md](post-runbook.md)` §4                      |
| 来源 RSS、模块关键词、摘要字数、`dedup`                        | `kit/engineering.json`                                       |
| LLM API                                          | `kit/config.json`（通常不入库；示例见 `config.example.json`）           |
| 字段协议、热点条数（8～12）、概要字数（尽量 ≤250 字）                  | `kit/prompts&templates/02_response_protocol.md`、`01_task.md` |
| 版面模板                                             | `kit/prompts&templates/agenda.md.j2`                         |
| 深度说明（管线扩展、历史约定）                                  | `[reference.md](reference.md)`                               |
| `kit` 目录说明                                       | `[kit/README.md](kit/README.md)`                             |


---

## 8. 脚本职责一览


| 脚本                     | 职责                                                                         |
| ---------------------- | -------------------------------------------------------------------------- |
| `daily_ai_frontier.py` | 解析 `--date` / `--steps`，按顺序调用各步                                            |
| `ingest.py`            | 抓取、关键词粗筛、篇内去重、与 **近 N 日** `summary.json` 对照的热点去重（`dedup.recent_summary_*`） |
| `summarize.py`         | 注入提示词、解析 LLM JSON、校验与补全轮、字段兜底、`summary.json`                               |
| `assemble.py`          | `summary.json` + 模板 → `agenda.md`                                          |
| `base_config.py`       | 路径与配置加载                                                                    |


---

## 9. LLM 输出协议（摘要）

`summarize` 期望根 JSON 包含 `deduplication`、`articles`、`blocks`。每条 `articles[]` 至少含：`point`、`one_liner`、`plain_explain`、`impact_1`、`impact_2`、`digest_for_outline`（**均为非空字符串**）；热点总量由模型按 `**drop_indices` 收敛在约 8～12 条（上限 12）**；`digest_for_outline` **尽量不超过约 250 字**，短稿勿灌水。

完整字段表与自检项以 `**02_response_protocol.md`** 为准；下方仅为结构示意：

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

