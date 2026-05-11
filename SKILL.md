---
name: ai-frontier-daily
description: >-
  每日 AI 前沿早报流水线：自动采集 RSS → LLM 摘要 → 渲染早报 Markdown → 飞书发布 + 群机器人 Webhook。
  这是一个定时任务 Skill，通过 cron 自动执行，无需用户主动触发。
disable-model-invocation: true
---

# AI 前沿早报（执行手册）

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

- 默认执行全部步骤：`ingest` → `filter_rank` → `summarize` → `assemble`
- 产物路径：`output/<DATE>/briefing.md`

### 2.2 分步执行（排错）

```bash
cd /Users/huangxingbiao/.qclaw/skills/ai-frontier-daily
python3 project-space/pipeline.py --steps ingest
python3 project-space/pipeline.py --steps filter_rank
python3 project-space/pipeline.py --steps summarize
python3 project-space/pipeline.py --steps assemble
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
| `output/<DATE>/briefing.md` | 对外发布的终稿 | ✅ 是 |
| `output/<DATE>/summary.json` | LLM 合并结果，用于飞书机器人推送 | 发布时需要 |
| `output/<DATE>/filtered_ranked.json` | 筛选排序后的中间产物 | 排错时用 |
| `output/<DATE>/ingested.jsonl` | 原始采集条目 | 排错时用 |

---

## 4. 发布后流程（标准执行）

脚本成功后，按以下步骤执行：

### 4.1 飞书知识库发布

**发布前必读**：Agent 必须完整读取 `output/<DATE>/briefing.md` 文件，不要用摘要或对话复述代替全文发布。

**同名去重**：目标路径下标题 `AI 前沿早报（YYYY-MM-DD）` 只保留一篇，已存在则覆盖。

检索已有文档：
```bash
DATE='YYYY-MM-DD'
SPACE_ID='your_space_id'      # 由大模型根据上下文判断
PARENT_TOKEN='your_parent_token'  # 由大模型根据上下文判断
lark-cli wiki nodes list --as user \
  --params "{\"space_id\":\"${SPACE_ID}\",\"parent_node_token\":\"${PARENT_TOKEN}\",\"page_size\":50}" \
  --page-all \
  -q ".data.items[] | select(.title | contains(\"AI 前沿早报（${DATE}）\")) | {title, node_token, obj_edit_time}"
```

**新建并归档**（未命中时执行）：

| 顺序 | 动作 |
|------|------|
| 1 | `lark-cli docs +create --as user --doc-format markdown --content "# 占位"` → 得到文档 `TOKEN` |
| 2 | `lark-cli docs +update --as user --doc $TOKEN --mode overwrite --new-title "AI 前沿早报（$DATE）" --markdown - < 早报文件路径` |
| 3 | `lark-cli wiki +move --as user --obj-type docx --obj-token $TOKEN --target-space-id "$SPACE_ID" --target-parent-token "$PARENT_TOKEN"` |
| 4 | 返回文档链接给用户 |

**参数说明**：
- 文档标题：`AI 前沿早报（YYYY-MM-DD）`
- `space_id` / `parent_node_token`：由大模型根据对话上下文判断（非硬编码）
- 账号模式：`--as user`（勿用 Bot token）

---

### 4.2 群机器人 Webhook 推送

发布完成后必须向群内推送富文本通知：

```bash
WEBHOOK=$(cat config/secrets.json | python3 -c "import sys, json; print(json.load(sys.stdin)['feishu']['bot_webhook'])")

curl -X POST "$WEBHOOK" \
  -H "Content-Type: application/json" \
  -d '{
    "msg_type": "post",
    "content": {
      "post": {
        "zh_cn": {
          "title": "早报：AI 前沿日报（YYYY-MM-DD）",
          "content": [
            [{"tag": "text", "text": "今日 AI 前沿早报已发布，"}],
            [{"tag": "a", "text": "点击查看详情", "href": "https://xxx.feishu.cn/…"}]
          ]
        }
      }
    }
  }'
```

---

### 4.3 流程小结

| 步骤 | 动作 |
|------|------|
| 1 | 读取终稿确认内容 |
| 2 | 发布到飞书知识库 |
| 3 | 群机器人 Webhook 推送 |
| 4 | 返回文档链接给用户 |

---

## 5. 配置说明

所有配置分为两类：

| 配置类型 | 位置 | 是否可提交 Git |
|----------|------|----------------|
| **业务配置**（RSS 源、模块、去重策略等） | `project-space/config/config.json` | ✅ 是 |
| **敏感信息**（API Key、Webhook） | `config/secrets.json` | ❌ 否（已 gitignore） |
| **发布目标**（知识库 space_id、parent_token） | 对话上下文 | 由大模型自行判断 |

### 5.1 首次配置

1. **复制敏感配置模板**：
   ```bash
   cp config/secrets.example.json config/secrets.json
   ```

2. **编辑 `config/secrets.json`**，填入你的真实值：
   ```json
   {
     "llm": {
       "api_key": "sk-your-real-api-key",
       "base_url": "https://api.deepseek.com",
       "model_name": "deepseek-chat"
     },
     "feishu": {
       "bot_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-token"
     }
   }
   ```

   **注意**：飞书知识库发布目标（`space_id`、`parent_node_token`）不在配置文件中，由大模型根据对话上下文自行判断。详见 `extension/post-runbook.md`。

### 5.2 配置索引

| 需求 | 位置 |
|------|------|
| 发布后流程（含 Webhook、知识库发布） | `extension/post-runbook.md` |
| RSS 来源、模块、去重策略 | `project-space/config/config.json` |
| LLM API（Key/BaseUrl/Model）| `config/secrets.json` |
| Webhook | `config/secrets.json` |
| 知识库发布目标 | 大模型根据对话上下文自行判断 |
| 筛选排序提示词 | `project-space/prompts/filter_ranker.md.j2` |
| 摘要提示词 | `project-space/prompts/summarizer.md.j2` |
| 早报模板 | `project-space/config/briefing-template.md.j2` |

---

## 6. 异常速查

| 现象 | 建议 |
|------|------|
| 脚本非 0 退出 | 检查虚拟环境、依赖完整性；查看 stderr |
| `ingested.jsonl` 为空 | 当日源站无命中或网络失败；告知用户「暂无采集结果」 |
| `filter_rank` 失败 | 检查 `config/secrets.json` 中的 LLM 配置 |
| `summarize` 失败 | 检查 `config/secrets.json` 中的 LLM 配置；修复后重跑 |
| 无早报文件 | 按 §2.2 分步执行，定位中断步骤 |
| 飞书发布失败 | 确认大模型已正确识别目标知识库（space_id、parent_node_token）|
| Webhook 推送失败 | 检查 `config/secrets.json` 中的 `feishu.bot_webhook` |

---

## 7. 安全与敏感信息

| 配置项 | 用途 | 所在文件 |
|--------|------|----------|
| `llm.api_key` | LLM API 认证 | `config/secrets.json`（gitignore） |
| `feishu.bot_webhook` | 飞书群机器人推送 | `config/secrets.json`（gitignore） |
| 知识库 `space_id` / `parent_node_token` | 飞书知识库发布目标 | 大模型根据对话上下文自行判断 |

**注意**：`config/secrets.example.json` 是模板文件（可提交），`config/secrets.json` 是真实配置（已 gitignore）。