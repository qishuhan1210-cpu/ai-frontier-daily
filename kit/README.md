# kit — 项目配置、提示词与模版

本目录为**单一入口**：工程配置、本地密钥示例、LLM 提示词 Markdown 与 Jinja2 模版均在此维护。路径与 **`engineering.json`** 解析由 **`scripts/base_config.py`** 集中导出，业务脚本勿写死目录名字符串。

---

## 顶层文件

| 文件 | 内容 |
|------|------|
| **`engineering.json`** | 工程管线配置：去重、assembly（模块/摘要/时间窗）、公开 RSS、来源与 URL 规则 |
| **`config.example.json`** | API 密钥与运行参数示例；本地复制为 **`config.json`** 并填写（`config.json` 已 gitignore） |

---

## `prompts&templates/` — 提示词与 Jinja 模版

Markdown 与 `.j2` **共置于此目录**（不再拆分顶层 `prompts/`、`templates/`）。均使用 [Jinja2](https://jinja.palletsprojects.com/)，渲染模版时 **`autoescape` 关闭**（Markdown / JSON 字面量）。

| 文件 | 说明 |
|------|------|
| **`01_task.md`**、`**02_response_protocol.md`** | 拼入 LLM **User 消息**的事项与协议正文；由 `summarize.build_user_prompt` 读取 |
| **`agenda.md.j2`** | 最终早报 `agenda.md` 的完整版式；由 `assemble.py` 注入变量 |
| **`system.md.j2`** | 统一摘要管线 **System** 提示；`summarize.build_system_prompt` 渲染 |
| **`runtime_injection.md.j2`** | 统一摘要 **User** 消息末尾的「运行时注入」段 |

- 改早报版式 → **`agenda.md.j2`**
- 改 System / 运行时注入措辞 → **`system.md.j2`**、**`runtime_injection.md.j2`**
- 改任务步骤与根 JSON 协议 → **`01_task.md`**、**`02_response_protocol.md`**

早报模版上下文：`section.entries` / `unknown.entries`（条目列表）；勿使用变量名 `items`，以免与 Jinja 内建冲突。
