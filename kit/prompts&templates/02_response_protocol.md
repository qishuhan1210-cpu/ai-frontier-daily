# 响应协议（LLM 输出 · 工程消费）

本文定义 **唯一合法根 JSON** 的形状与字段约束。工程侧 `summarize.py` 解析后写入 `summary.json`（`items` + `blocks`）；`assemble.py` 读取拼版。

---

## 根对象

仅允许一个 JSON 对象，**禁止** Markdown 代码围栏、禁止 JSON 外任何字符。

### `deduplication`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `drop_indices` | number[] | 是 | 要丢弃的原始 `index`（含**重复**与**价值筛选裁掉**的条目）；可为空数组 |
| `notes` | string | 否 | 去重与筛选理由简述；若执行 TOP10 截断，须体现「价值排序保留至多 10 条」 |

### `articles`

| 规则 | 说明 |
|------|------|
| 条数上限 | **`articles` 数组长度 ≤ 10**：模型须在去重后按价值保留**最优 TOP10**（见 `01_task.md`）；超出部分须通过 `drop_indices` 丢弃，不得输出更多 `articles` 条目 |
| 条目范围 | **仅保留稿**：每条对应清单中**未被 `drop_indices` 收录**且**进入 TOP10 价值保留集**的 `index` |
| `source_index` | 必填，等于清单中的原始 `index` |
| 语言 | 所有字符串字段中文 |

#### 单条 `articles[]` 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_index` | number | 原始编号 |
| `point` | string | ~30 字，从业者视角为何值得看 |
| `one_liner` | string | ~25 字，客观概括事件 |
| `plain_explain` | string | ~50 字，白话 |
| `impact_1` | string | ~30 字 |
| `impact_2` | string | ~30 字 |
| `digest_for_outline` | string | 可选；无 RSS 长摘要时可作概要素材 |

### `blocks`

#### `blocks.header`

| 字段 | 类型 | 说明 |
|------|------|------|
| `tags_full` | string | 含 `#AI早报` 及 3～8 个当日标签，空格分隔 |
| `data_sources` | string | 清单中**真实出现**的来源媒体名，` · ` 分隔，勿虚构 |

#### `blocks.footer`

键名必须与运行时注入的 **模块 id 列表**一致（一般为 `hardware` / `model` / `ai_engineering` / `industry` / `policy`）。

| 键 | 内容 |
|----|------|
| 各 module id | 该模块今日一句话速览，≤40 字；无稿写「今日暂无相关报道」 |

---

## 示例（结构示意）

```json
{
  "deduplication": {
    "drop_indices": [],
    "notes": ""
  },
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
    "header": {
      "tags_full": "#AI早报 #大模型",
      "data_sources": "量子位 · 36氪"
    },
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

### 硬性校验（模型自检）

1. `articles` 中每条 `source_index` 不得出现在 `drop_indices` 中。  
2. `blocks.footer` 键齐全，与注入的模块 id 一致。  
3. `blocks.header.data_sources` 仅含清单中出现过的来源名。
