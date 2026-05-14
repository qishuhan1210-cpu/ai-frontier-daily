# 「AI 前沿早报」项目优化 - TODO & CHANGELOG

## 📋 TODO List

## 📝 CHANGELOG

### v1.1.0 - 2026-05-11
- **内容层优化**
  - 合并 `point`/`one_liner` 为 `headline`（约60字）
  - 合并 `impact_1`/`impact_2` 为 `impacts`（约60字）
  - 新增 `tags` 字段，建立标签体系（#企业硬件、#协议基建、#AI落地、#地缘政治等）
  - 强化 `plain_explain`（约80字），面向小白用户解释
  - 放宽 `digest_for_outline` 至300字，深化摘要信息

- **选题纠偏**
  - 在 `engineering.json` 中添加 `filter_keywords.exclude` 配置
  - 剔除基金、股票、消费电子等非AI核心内容
  - `ingest.py` 添加 `_contains_excluded_keywords()` 函数实现选题过滤

- **热点逻辑优化**
  - 新增热点话题持续推送机制
  - 配置项：`hot_topic_enabled`、`hot_topic_days`、`hot_topic_repeat_threshold`
  - 连续多日出现的热门话题可再次推送

- **提示词文件更新**
  - 更新 `01_task.md`：添加选题纠偏规则和标签体系要求
  - 更新 `02_response_protocol.md`：定义新字段结构
  - 创建 `PROMPT_ANALYSIS.md`：提示词职责分析文档

- **工程配置更新**
  - `engineering.json` 添加 `tags` 配置段
  - `engineering.json` 添加 `filter_keywords` 配置
  - `engineering.json` 添加热点逻辑配置

- **脚本更新**
  - `summarize.py`：支持新字段结构（headline、impacts、tags）
  - `ingest.py`：添加选题纠偏和热点持续推送功能
  - 创建 `unified_pipeline.py`：一站式执行 ingest → summarize → assemble

### v1.0.0 - 2026-05-11
- 初始化项目结构
- 完成飞书CLI集成
- 实现基本早报流水线（ingest → summarize → assemble）
- 支持飞书文档发布和机器人推送
- 创建 project-space、extension、references 目录
