# 「AI 前沿早报」项目优化 - TODO & CHANGELOG

## 📋 TODO List

### 内容层优化

#### 结构与格式
- [x] 合并重复内容：将"point"与"一句话"合并为一个更长的"headline"
- [ ] 统一排版格式：原文链接、影响部分直接接在正文后，不换行
- [ ] 规范二级序号：统一使用"1.1、1.2、1.3"的格式

#### 内容质量
- [x] 深化新闻概要：丰富摘要信息，减少用户点击原文的成本
- [x] 落实"白话理解"：面向小白用户解释企业新闻和生僻概念
- [ ] 选题范围扩展：从"AI Agent"放宽至"科技/AI行业"相关

#### 标签与分类
- [x] 建立标签体系：梳理清晰稳定的标签系统
- [x] 应用新标签：企业/用户硬件、协议/基建、AI落地与协作、地缘政治

#### 选题纠偏
- [x] 剔除非相关选题：移除基金、纯硬件等内容
- [ ] 明确"地缘政治"定义：严格限定为国家间竞争与战争
- [x] 聚焦AI核心选题：内容聚焦AI前沿、AI落地及人机协作

#### 热点逻辑优化
- [x] 连续多日热门再推送：支持持续热点话题的再次推送

### 工程改造与架构调整

#### 1、目录结构重构
- [x] 创建 project-space 目录
- [x] 创建 extension 目录
- [x] 创建 references 目录
- [ ] 工程文件移入 project-space 目录

#### 2、提示词分析与优化
- [x] 分析 01_task.md、02_response_protocol.md、system.md.j2、runtime_injection.md.j2 的职责
- [x] 评估合并方案（保持四文件结构）
- [x] 更新提示词文件支持新字段结构

#### 3、架构策略调整
- [ ] 剥离提示词工程逻辑
- [ ] 延后非核心改造任务

#### 4、研发流程合并
- [x] 合并 ingest.py、summarize、assemble 三个步骤（创建 unified_pipeline.py）

---

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
