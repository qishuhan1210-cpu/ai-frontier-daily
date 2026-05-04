# 响应协议（LLM 输出 · 工程消费）

定义 **唯一合法根 JSON**（无 Markdown 围栏、无 JSON 外字符）。`summarize.py` 解析写入 `summary.json`；`assemble.py` 拼版。

---

## 根对象

仅含：`deduplication`、`articles`、`blocks`。

### `deduplication`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `drop_indices` | number[] | 是 | 丢弃的原始 `index`（重复 + 价值筛选裁掉）；可 `[]` |
| `notes` | string | 否 | 去重/筛选简述；若执行 TOP10 截断须写明依据；若有极少数豁免须在 notes 点名 |

### `articles`

| 规则 | 说明 |
|------|------|
| **条数** | **长度 ≤ 10**。去重后仍多于 10 条时，按 **热度（讨论度、传播面、时效）× 影响度（产业/政策/技术栈波及面）** 综合排序，**只保留 TOP10**，其余 `index` 全部进入 `drop_indices` |
| **与保留 index 对齐（硬约束）** | 设去重后保留 index 集合为 **K**，则 **`articles` 条数必须等于 K 的元素个数**，且 **`source_index` 与 K 一一对应（无重复、无遗漏）**。漏一条或多半条均视为 **无效输出** |
| **板块** | **尽量**每日各板块至少入选 1 条（清单在该板块完全无稿则可跳过）；**同一板块入选 ≤ 4 条**，与其它约束一并满足 |
| `source_index` | 必填，对应清单原始 `index` |
| 语言 | 字符串一律中文 |

#### 单条 `articles[]` 字段（全部为硬必填）

以下字段在 **每一条** `articles[]` 中 **必须出现且值为非空字符串**（经 `strip()` 后长度 ≥1）。**禁止** `""`、禁止省略键、禁止仅用「同上」「待补充」。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `source_index` | number | 必填 | 清单编号 |
| `point` | string | ~30 字 | 从业者视角：为何值得看 |
| `one_liner` | string | ~25 字 | 客观一句：发生了什么 |
| `plain_explain` | string | ~50 字 | 白话说明背景与要点 |
| `impact_1` | string | ~30 字 | 影响/后果一 |
| `impact_2` | string | ~30 字 | 影响/后果二 |
| `digest_for_outline` | string | **约 300 字（280～320 汉字为宜）** | **概要**：供早报「概要」正文使用；独立压缩稿（删开场媒体套话、重复引述，保留事实、主体、时间、数字与可核验结论），**禁止**与 title/one_liner 简单重复堆砌 |

**填充率目标**：本回合 `articles` 内上述 **6×N** 个字符串槽位，非空率应 **≥95%**；工程侧会校验，不达标将要求整份 JSON 重写。**豁免**（整条不写、仍进保留集）仅允许在原文极度匮乏且已在 `deduplication.notes` 说明——**不得滥用**。

---

### `blocks`

#### `blocks.header`

| 字段 | 类型 | 说明 |
|------|------|------|
| `tags_full` | string | 含 `#AI早报` + 当日 3～8 个标签，空格分隔；**非空** |
| `data_sources` | string | 仅列清单中 **真实出现** 的来源媒体，` · ` 分隔；**非空** |

#### `blocks.footer`

键名与注入的 **模块 id** 一致（常见：`hardware` / `model` / `ai_engineering` / `industry` / `policy`）。每键一句当日模块速览，≤40 字；无稿写「今日暂无相关报道」。**每个键必须存在且字符串非空。**

---

## 结构示例（禁止照抄空字符串；以下为占位示意，真实输出须写满）

```json
{
  "deduplication": { "drop_indices": [], "notes": "" },
  "articles": [
    {
      "source_index": 0,
      "point": "（从业者视角一句，非空）",
      "one_liner": "（客观概括，非空）",
      "plain_explain": "（白话，非空）",
      "impact_1": "（影响一，非空）",
      "impact_2": "（影响二，非空）",
      "digest_for_outline": "（约300字压缩概要，非空）"
    }
  ],
  "blocks": {
    "header": { "tags_full": "#AI早报 #大模型", "data_sources": "量子位 · 36氪" },
    "footer": {
      "hardware": "今日暂无相关报道",
      "model": "（≤40字模块速览）",
      "ai_engineering": "今日暂无相关报道",
      "industry": "（≤40字）",
      "policy": "今日暂无相关报道"
    }
  }
}
```

### 硬性自检（输出前逐项执行）

1. `articles.length` ≤ 10，且每条 `source_index` ∉ `drop_indices`。  
2. 设保留 index 集合为 K：**`articles` 条数等于 K 的元素个数**，且 **`source_index` 去重后等于 K**。  
3. **TOP10**：若输入去重后仍 >10 条，必须完成热度×影响度排序截断，且 `notes` 体现截断；截断后自查 **每板块条数 ≤ 4**。  
4. **六项全满**：对每条 article，`point`、`one_liner`、`plain_explain`、`impact_1`、`impact_2`、`digest_for_outline` 均为 **非空字符串**；`digest_for_outline` 字数约 **300**（宜 280～320）。  
5. `blocks.header.tags_full`、`blocks.header.data_sources` 非空；`blocks.footer` 键齐全且每值非空；`data_sources` 不虚构。
