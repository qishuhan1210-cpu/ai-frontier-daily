# 早报终稿生成后的发布流程

在 `output/<DATE>/` 目录下的早报 Markdown 文件已由 `assemble`（或一键 `pipeline.py`）成功产出后，按本节执行。**内容与结构始终以该文件为准**；除非脚本失败且用户明确要求手工整理，否则不要用对话凭空重写终稿。**标准对外流程为 §2～§4 连贯执行**：发布至飞书后 **必须**完成 §4 群机器人推送（`msg_type: post`）。

**发布目标判定**：飞书知识库发布的 `space_id` 和 `parent_node_token`**不由配置文件硬编码**，由大模型根据对话上下文自行判断（例如用户提及的部门、项目、话题等线索）。Webhook 从 `.env` 读取。

---

## 1. 发布前必读

- **路径**：`$SKILL_DIR/output/$DATE/` 目录下的早报 Markdown 文件（`DATE` 为 `YYYY-MM-DD`）。
- **Agent 在对外发布（含飞书）前必须完整读取该文件**，不要用摘要或对话里的复述代替全文去做覆盖发布。

---

## 2. 飞书发布

将终稿同步至飞书知识库。

**通用飞书 / `lark-cli` 规范**（命令分层、Shortcut 优先、禁止裸 `curl`、exit 10、Wiki 删除的 `obj_token` 流程等）以 skill **[feishu-operations-skill](../feishu-operations-skill/SKILL.md)** 为准；可执行模板见同级 **[常用命令示例.md](../feishu-operations-skill/references/常用命令示例.md)**（含「Shortcut 覆盖缺口与兜底」「Wiki 删除（无 Shortcut 时）」），元数据表见 **[基础元信息库.md](../feishu-operations-skill/references/基础元信息库.md)**。本节只保留早报流水线环境变量名、同名去重、四步发布与禁止项。

### 2.0 同名去重

目标路径下标题 `AI 前沿早报（$DATE）` 只保留一篇：已存在则 **覆盖**，不新建第二篇。

- **检索**：执行以下命令（`space_id` 和 `parent_node_token` 由大模型根据上下文自行判断）：

  ```bash
  DATE='YYYY-MM-DD'
  SPACE_ID='your_space_id'      # 由大模型根据上下文判断
  PARENT_TOKEN='your_parent_token'  # 由大模型根据上下文判断
  lark-cli wiki nodes list --as user \
    --params "{\"space_id\":\"${SPACE_ID}\",\"parent_node_token\":\"${PARENT_TOKEN}\",\"page_size\":50}" \
    --page-all \
    -q ".data.items[] | select(.title | contains(\"AI 前沿早报（${DATE}）\")) | {title, node_token, obj_edit_time}"
  ```

  将 `DATE` 换成实际日期（如 `2026-05-04`），`SPACE_ID` 和 `PARENT_TOKEN` 由大模型根据对话上下文确定。返回结果中包含 `node_token` 即为已有文档。`obj_edit_time` 是 Unix 时间戳（秒级），代表文档最后一次编辑时间。

- **已命中**：
  1. 取 `obj_edit_time` 最大的 `node_token` 作为有效文档（同名仅保留该篇）→ 仅做 §2.1 步骤 2、4（跳过占位创建与 `wiki +move`）。
  2. **其余同名旧文档直接删除**，勿长期保留多份同标题。完整删除流程（`obj_token`、`GET`/`DELETE`、131005 校验）见 **[feishu-operations-skill/references/常用命令示例.md](../feishu-operations-skill/references/常用命令示例.md)** 中 **「Wiki 删除（无 Shortcut 时）」**；`node_token` 来自上表检索或 URL 中 `/wiki/` 后片段。

- **未命中**：走 §2.1 四步。

### 2.1 新建并归档（§2.0 未命中时）


| 顺序  | 动作                                                                                                                           |
| --- | ---------------------------------------------------------------------------------------------------------------------------- |
| 1   | `lark-cli docs +create --as user --doc-format markdown --content "# 占位"` → 得到文档 `TOKEN`                                      |
| 2   | `lark-cli docs +update --as user --doc $TOKEN --mode overwrite --new-title "AI 前沿早报（$DATE）" --markdown - < 早报文件路径`        |
| 3   | `lark-cli wiki +move --as user --obj-type docx --obj-token $TOKEN --target-space-id "$SPACE_ID" --target-parent-token "$PARENT_TOKEN"`（参数由大模型根据上下文判断）|
| 4   | 把文档/知识库可调链接返回给用户                                                                                                             |


### 2.2 参数常量

| 项    | 说明                                     |
| ---- | --------------------------------------- |
| 文档标题 | `AI 前沿早报（YYYY-MM-DD）`                   |
| 知识库 `space_id` | 由大模型根据对话上下文自行判断（非硬编码） |
| 父节点 `parent_node_token` | 由大模型根据对话上下文自行判断（非硬编码） |
| 账号模式 | `--as user`（勿用 Bot token，否则 wiki 权限易失败） |


### 2.3 禁止

- Bot token 建文档再移 wiki。
- `docs +create` 一次塞入超长正文；应先占位再 `+update overwrite`。
- 要求归档却不移入知识库。
- 不做 §2.0 就 `docs +create`，造成同名多篇。

---

## 3. 向用户回传

完成 **§2、§4** 后，将 `DOC_URL`（可调文档/知识库链接）返回给用户。若本次任务从始至终只要本地早报文件、不走飞书，则不适用 §2～§4，直接向用户说明本地路径即可。

---

## 4. 群机器人 Webhook 推送（发布后通知群内）

§2 完成后 **必须**执行：向群内推一条 **富文本（`msg_type: post`）**。`post` 支持标题、可点链接与多段正文；不会像分享卡片那样带封面/摘要，但比纯文本清晰。

本约定：**飞书机器人仅启用「自定义关键词」**，**关闭签名校验**；消息须含后台配置的关键词（脚本将 `早报：` 写在标题中，须与后台一致）。

官方说明：[自定义机器人](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)。请求体 ≤20KB；成功时响应 `"code":0`。

### 4.1 脚本（推荐）

工程逻辑见 `extension/push_feishu_bot.py`：读取 `output/<DATE>/summary.json` 的 `blocks.footer`（按 `hardware` → `model` → `ai_engineering` → `industry` → `policy` 顺序拼摘要），与 `--doc-url` 组装 `post` 并 `POST` 到 Webhook。

在技能根目录执行（当日 `summary.json` 已随流水线产出）：

```bash
python3 extension/push_feishu_bot.py --date YYYY-MM-DD --doc-url 'https://xxx.feishu.cn/…'
```


| 参数 / 环境变量                                  | 含义                     |
| ------------------------------------------ | ---------------------- |
| `--date`                               | `YYYY-MM-DD`           |
| `--doc-url`                            | §2 得到的飞书文档 URL         |
| `FEISHU_BOT_WEBHOOK` / `--webhook` | 自定义机器人地址（从 `.env` 读取） |


---

## 5. 与主手册的衔接

- 流水线执行、分步排错、产物索引：**[SKILL.md](../SKILL.md)**
- 飞书 / `lark-cli` 通用规范与命令模板：**[feishu-operations-skill/SKILL.md](../feishu-operations-skill/SKILL.md)**（及同级 `references/` 元信息、常用命令示例）
- 若早报文件不存在或脚本失败：不要在 Chat 里杜撰终稿，按 **SKILL.md** 中的分步执行与异常速查处理

