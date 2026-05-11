# AI 前沿早报（ai-frontier-daily）

编排 **ingest → summarize → assemble** 流水线：抓取与过滤 RSS、LLM 摘要、渲染早报 Markdown 终稿。可作为独立脚本使用，也可配合 Cursor Agent Skill（见 [`SKILL.md`](SKILL.md)）。

## 流水线

| 步骤 | 脚本 | 默认产出 |
|------|------|----------|
| ingest | `project-space/ingest.py` | `output/<date>/ingested.jsonl` |
| summarize | `project-space/summarize.py` | `output/<date>/summary.json` |
| assemble | `project-space/assemble.py` | `output/<date>/` 目录下的早报 Markdown |

一键执行：

```bash
.venv/bin/python3 project-space/pipeline.py --date YYYY-MM-DD
```

## 环境

- Python 3.10+（建议）
- 依赖见 [`project-space/requirements.txt`](project-space/requirements.txt)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 配置

1. 复制 `kit/config.example.json` 为 **`kit/config.json`**（该文件已列入 `.gitignore`，勿提交密钥）。
2. 填入兼容 OpenAI API 的 `api_key`、`base_url`、`model_name` 等。
3. 工程与 RSS 规则见 [`kit/engineering.json`](kit/engineering.json)；提示词与模版见 [`kit/README.md`](kit/README.md)。

## 文档

- 字段与扩展规则：[`references/reference.md`](references/reference.md)
- `kit` 目录说明：[`kit/README.md`](kit/README.md)

## 许可证

若公开发布，建议在仓库根目录添加 `LICENSE` 并选用合适条款（如 MIT、Apache-2.0）。
