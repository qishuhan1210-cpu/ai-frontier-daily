## 变更日志

### 2026-05-16 (commit: -)，作者：wghlmg1210

#### 研发工程

- **utils/domain** - 新增数据模型层，建立继承体系
  - NewsItem（基类）→ FilteredItem → SummaryItem 三级继承
  - 每个类提供 `from_dict()` 静态方法
  - FilteredItem 新增 `from_news_and_llm()` 工厂方法
  - SummaryItem 新增 `from_filtered_and_llm()` 和 `extract_articles()` 方法
  - 新增 FilterStats、BriefingMeta 辅助模型
- **ingest** - 全程使用 NewsItem 对象处理
  - `dedup()` / `dedup_recent()` 参数改为 `List[NewsItem]`
  - 字段访问从字典改为属性（`it.get('url')` → `it.url`）
- **filter_rank** - 迁移到 domain 模型
  - 使用 `NewsItem.from_dict()` 加载数据
  - 使用 `FilteredItem.from_news_and_llm()` 合并 LLM 结果
  - 使用 `FilterStats.from_counts()` 生成统计信息
  - 废弃 `sub_topic`，改用 `main_section` + `sub_section`
- **summarize** - 迁移到 domain 模型
  - 使用 `FilteredItem.from_dict()` 加载数据
  - 使用 `SummaryItem.from_filtered_and_llm()` 合并结果
  - `_merge_items()` 独立为专用方法
- **assemble** - 使用 BriefingMeta 数据结构
  - `_load_items()` 返回 `BriefingMeta` 对象
  - `_build_context()` 接收 `BriefingMeta` 参数
- **config** - 重构为三层架构
  - 模块层：public_feeds、dedup、filter_rank、assembly
  - 链接层：llm 客户端配置
  - 协议层：protocol（字段协议）、classification（分类体系）、tags（标签词库）
- **base_config** - AppConfig 重构，支持三层配置访问
  - `config.modules`：模块层配置
  - `config.links`：链接层配置
  - `config.protocols`：协议层配置
- **pipeline** - 更新模块初始化方式，移除 date_str 参数

#### 提示词工程

- **filter_ranker.md.j2** - 字段协议更新
  - `sub_topic` → `main_section` + `sub_section`
  - 更新分类体系为 "4+1" 层级架构
- **summarizer.md.j2** - 标签字段更新
  - 新增 `vertical_tags`、`general_tags` 字段
- **briefing-template.md.j2** - 渲染垂类/通用标签

---

### 2026-05-16 (commit: -)，作者：wghlmg1210

#### 研发工程

- **base_config** - 重构 TemplateConfig，移除 assembly_modules 耦合
  - 构造函数取消 assembly_modules 参数，改为纯依赖 classification_data
  - classification_rules 改为返回分类对象列表（而非表格字符串）
  - tag_options 改为返回列表（而非逗号分隔字符串）
- **prompt_loader** - 新支持 frontmatter `$$$$|` 分隔符格式
  - parse_frontmatter 重构支持新格式解析
  - load_with_config 改为动态从 classification_rules 生成 coverage/ids_str/module_names/tag_options
- **assemble** - modules 来源改为 config.template.classification_rules；coverage_line 生成逻辑内联化
- **filter_rank** - valid_sub_topics 改为 list 类型，来源迁移至 config.template.classification_rules
- **push_feishu_bot** - footer_modules 取完整 module name（取消前两字符截断）

#### 提示词工程

- **filter_ranker.md.j2** - frontmatter 改用 `$$$$|` 新格式；sub_topic 枚举和分类规则表格改为循环渲染
- **summarizer.md.j2** - frontmatter 改用 `$$$$|` 新格式

#### 研发工程（测试）

- **test_prompt_injection** - frontmatter 格式统一更新为 `$$$$|`；mock_config 简化，移除 modules 列表
- **test_config_classes** - 断言改为验证 classification_rules 返回列表

---

### 2026-05-15 (commit: -)，作者：wghlmg1210

#### 研发工程

- **base_config** - 新增 TemplateConfig，聚合分类/标签/coverage 生成逻辑
  - TemplateConfig 内联 classification 与 tags 解析，暴露 coverage / ids_str / module_names / tag_options / classification_rules 五个 property
  - AppConfig 新增 `template` 子属性，管理全部模板变量；删除独立的 `header_coverage` property
- **prompt_loader** - PromptLoader 新增 `load_with_config()` 方法，从 `config.template` 统一提取变量注入
- **config** - 版本升至 2.3；新增 `classification`（5 个主分类节点）与 `tags`（6 个 tag 选项 + 两套白名单）预留区块
- **filter_rank** - `_build_prompts()` 改用 `PromptLoader().load_with_config()`，移除手动变量拼装
- **summarize** - `_build_prompts()` 改用 `PromptLoader().load_with_config()`，`ids_str` 拼接迁移至注入器
- **assemble** - `coverage_line` 取值改为 `config.template.coverage`
- **utils/__init__** - 新增 TemplateConfig 导出

#### 提示词工程

- **summarizer** - 修复 Critical Bug：system prompt tag 体系（旧：企业/用户硬件等6类）与 user prompt（新：融资投资等6类）不一致，统一为新体系
- **summarizer** - `blocks.footer` 描述及示例中过时模块 ID (`ai_engineering`→`application`、`industry`→`investment`) 修正
- **summarizer** - system/user 两处 tag 选项改为 `{{ tag_options }}` 动态注入
- **filter_ranker** - `sub_topic` 枚举及分子主题定义表格改为 `{{ module_names }}` / `{{ classification_rules }}` 动态注入，保留硬编码内容为 else 兜底
- **briefing-template** - `## 六、其他·未分类` 序号改为 `{{ sections|length + 1 }}` 动态计算

#### 研发工程（测试）

- **test_prompt_injection** - 新增，覆盖 TemplateConfig 所有 property 及 PromptLoader.load_with_config() 渲染行为，共 12 个用例
- **test_config_classes** - `test_header_coverage` 更新为 `test_template_coverage`，断言改用 `config.template.coverage`
- **test_config** - 移除对不存在的 `TEMPLATES_DIR` 和 `get_module_by_id()` 的错误引用

---

### 2026-05-15 (commit: -)，作者：wghlmg1210

#### 研发工程

- **base_config** - 重构配置系统，分散加载函数统一为 AppConfig + ConfigDict
  - 新增 AppConfig，统一管理 feeds/dedup/llm/filter_rank/assembly 配置
  - 新增 ConfigDict，支持点访问配置值
  - 新增模板路径常量 TEMPLATE_BRIEFING/FILTER_RANK/SUMMARIZE
  - 删除所有 load_xxx() 分散配置函数
- **config** - 重构，JSON 迁移至 YAML；新增 llm、filter_rank 配置段
- **utils/__init__** - 重构导出：BaseModule→WorkModule；新增 AppConfig/ConfigDict/TemplateRenderer
- **prompt_loader** - 新增 TemplateRenderer；新增 render_and_parse 方法
- **work_module** - 新增，原 base.BaseModule 重命名迁移
- **assemble** - 重构，接入 AppConfig 与 TemplateRenderer；删除向后兼容函数
- **filter_rank** - 重构，接入 AppConfig；配置项动态化；删除向后兼容函数
- **ingest** - 重构，接入 AppConfig；移除分散配置调用
- **summarize** - 重构，接入 AppConfig；LLM 参数配置化；删除向后兼容函数
- **test_config** - 新增 AppConfig 自测脚本
- **test_config_classes** - 新增配置类单元测试
- **.gitignore** - 新增 CHANGELOG.md、todolist/ 忽略规则
- **TODO&CHANGELOG** - 删除，拆分为独立文件管理

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
