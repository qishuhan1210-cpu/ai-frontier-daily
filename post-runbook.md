# Post-agenda runbook（样本 · 可入库）

Agent 在流水线成功产出 `output/<DATE>/agenda.md` 之后，应读取 **`post-runbook.md`**（若不存在则先按本样本创建一份）。

---

## Case 说明（示例）

**场景：用户只要本地 Markdown、不要求发到飞书**

- 确认 `output/<DATE>/agenda.md` 存在；向用户说明完整路径或按其需求摘录要点。
- **不执行** `lark-cli`、wiki 移动等任何外部发布步骤。

其他场景（飞书创建/覆盖/wiki 归档、固定标题格式、回传链接样式等）请在个人的 **`post-runbook.md`** 中自行维护。

---

## 群机器人 Webhook 推送（文档发布后须执行）

飞书 **自定义机器人** 使用群内向导生成的地址：`https://open.feishu.cn/open-apis/bot/v2/hook/<token>`。通过 **`POST`**、`Content-Type: application/json` 向该 URL 发请求即可推送到群内（文本 / 富文本 / 卡片等）。官方文档：[自定义机器人使用指南](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)。

**要点摘要**

| 项 | 说明 |
|----|------|
| 请求 | `POST`，请求体 JSON，`code == 0` 表示成功 |
| 体积 | 单次请求体建议 **≤ 20KB** |
| 安全（本仓库约定） | 机器人**仅开自定义关键词**，推送正文须命中关键词；详见 **`post-runbook.md`** §4 |
| 频率 | 约 **100 次/分钟、5 次/秒**（官方建议避开整点高峰以免限流） |

**早报 Webhook（必做）**：§2 得到 **`DOC_URL`** 后，按 **`post-runbook.md`** §4 运行 **`scripts/push_feishu_bot.py`**。**`FEISHU_BOT_WEBHOOK`**；勿写入 `config.example.json`。

---

## 与主手册的衔接

编排流水线、排错与产物约定见 **[`SKILL.md`](SKILL.md)**。
