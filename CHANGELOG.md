## 变更日志

### 2026-06-06 (commit: -)，作者：wghlmg1210

#### 研发工程

##### 1. 自动化模块拆分重构（微信 & 小红书解耦）

- **main（删除）** - 删除单体入口文件，拆分为独立的微信、小红书 CLI 模块
- **wechat、xiaohongshu** - 新增独立 CLI 入口，各平台命令独立管理
- **wechat-publisher、xhs-publisher** - 新增各平台业务流程层，封装完整发布流程
- **actions** - 新增业务语义层，将浏览器操作组合为高层业务动作
- **base-browser** - 新增浏览器操作基类，提取通用操作；派生 `WechatBrowserOps`、`XhsBrowserOps` 两个平台子类
- **publisher（删除）** - 原有函数式 publisher 内化至各平台类中
- **package.json** - 命令脚本按平台拆分，新增 `wechat-*` / `xhs-*` 独立指令

##### 2. 小红书自动化深度构建

- **xhs-publisher、actions、base-browser** - 完整构建小红书图文笔记发布链路：登录态检测 → 图片上传 → 填标题正文 → 标签选择 → 定时发布配置 → 发布
- **xhs-publisher** - 新增 `summary.json` 驱动的正文自动生成；图片按 `quick-view` → `card-*` 顺序排列
- **xhs-publisher** - 新增定时发布逻辑：按配置时间判断是否需要定时，自动切换直接发布 / 定时发布模式
- **config** - 小红书 selector 全面更新，对齐最新创作者平台页面结构；新增定时发布、Tags 等配置项

##### 3. Vue 隐藏组件绕行方案（发布按钮）

- **base-browser（XhsBrowserOps.clickPublishBtn）** - `xhs-publish-btn` 为 Vue Web Component，内部 DOM 不可直接查询；改用 `boundingBox` 定位元素坐标后，通过 `page.mouse.click` 模拟点击右侧红色发布区域，绕过 Shadow DOM 限制

##### 4. 微信公众号模块修复

- **assemble** - 注释掉发布后自动打开文件的调用，修复流程意外弹窗问题
- **lark_commander** - 修复 `lark-cli` 路径引用，改用变量 `_LARK_CLI` 提升一致性

#### Skill 框架

##### 5. 流水线脚本调整

- **scripts/pipeline.sh** - 新增小红书定时发布步骤；微信入口切换至 `src/wechat.ts`；暂时注释飞书文档发布和群推送步骤，聚焦核心自动发布链路

---

### 2026-06-05 (commit: -)，作者：wghlmg1210

#### 研发工程

##### 1. 新增多平台浏览器自动化模块（project-space2）

- **main、auth、publisher、config** - 新增 `project-space2/`；支持微信公众号和小红书图文双平台自动发布；使用 TypeScript + Playwright，统一 CLI 入口（commander），配置集中到单一 YAML 文件

##### 2. 小红书截图脚本迁移并升级为 TypeScript

- **screenshot-redbook-cdp** - 从 `scripts/screenshot-redbook-cdp.js` 迁移至 `project-space2/src/services/screenshot-redbook-cdp.ts`；升级为 TypeScript，路径计算适配新目录层级

##### 3. 流水线脚本目录重组

- **news_frontier** - 从 `scripts/` 迁移至 `project-space/`，路径解析适配
- **publish2lark、publish2lark_base、push2group** - 从 `scripts/` 迁移至 `scripts/pipeline/`，`_PROJECT_ROOT` 路径上移一级适配

##### 4. lark_commander 路径查找修复

- **lark_commander** - 改用 `shutil.which` 动态查找 `lark-cli` 路径，兼容非 PATH 默认安装位置

#### Skill 框架

##### 5. 新增整合 pipeline 脚本

- **scripts/pipeline.sh** - 新增一键运行脚本；整合新闻采集 → 飞书文档 → 小红书截图 → 飞书群推送 → 微信草稿五个步骤

##### 6. 配置与文档同步更新

- **【移除事项】** 删除已被内化的 `render_wechat.sh`
- **【更新事项】** `.lobster` 工作流各步骤路径同步更新至新结构；`.gitignore` 补充 `project-space2/` 忽略规则、研发文档目录及 lobster 实例文件
- **【新增事项】** `docs/2026-06-03-安装playwright.md` - 新增 `project-space2` Playwright 自动化使用文档

---

### 2026-05-26 (commit: -)，作者：wghlmg1210

#### 研发工程

##### 1. 小红书截图功能接入（使用 Chrome APP & CDP 实现截图自动化）

- **screenshot-redbook-cdp.js** - 新增批量截图脚本；以 Chrome APP & CDP 作为底层驱动实现自动化截图，同时沉淀 PRD 和截图流程设计文档

##### 2. 早报输出拆分为三种格式（飞书 / 微信公众号 / 小红书）

- **assemble、base_config、utils/__init__** - Input / Output 命名统一；清理历史遗留模板文件；相关引用同步适配

#### Skill 框架

##### 3. SKILL & PIPELINE 重写：固定链路 + 扩展链路拆分

- **SKILL** - 工作流执行方式补充参数说明；产物表格拆分为确定产出 / 可选产出；分发脚本列表同步更新
- **PIPELINE** - 重构为「核心链路（固定）+ 分发链路（扩展）」双轨结构；扩展部分新增小红书截图步骤（§3.4）

---

### 2026-05-24 (commit: c5f62f5)，作者：wghlmg1210

#### 研发工程

##### 1. 新增公众号内联 HTML Jinja2 模板（html-anything基础模版的改造版本）

- **briefing-template-wechat-inline.html.j2** - 新增面向公众号的纯内联样式渲染模板
  - 基于html-anything产出的基础模版的基础上 进行改造得来
  - 当前默认 使用 wechat-inline 模版（for wechat公众号）
- **assemble** - `section.heading` 去除多余 `## ` 前缀，由模板自行控制标题层级
- 沉淀「微信公众号-html样式注意事项」文档

---

### 2026-05-24 (commit: eb9e95f)，作者：wghlmg1210

#### 研发工程

##### 1. 内化微信渲染（移除render_wechat外部依赖）
- 【移除事项】配置 & 工作流 & 说明文档：相应更新
  - secrets.example.json、ai-frontier-daily.example.lobster、PIPELINE.md
- 【内化事项】新增HTML模版 & 集成至 assemble 中
  - briefing-template-bold-navy.html.j2、assemble.py

---

### 2026-05-24 (commit: 35b3f7f)，作者：wghlmg1210

#### 研发工程

##### 1. SummaryCluster 自管理属性，解除对 NewsCluster 强依赖

- **domain** - SummaryCluster 移除 cluster 嵌套，改为自管理全部字段
- **summarize、assemble** - 构建/加载改用工厂方法

##### 2. 渲染层改用 SummaryCluster，移除旧版兼容

- **assemble** - 删除旧版 items 兼容代码，全链路使用 SummaryCluster

##### 3. 删除 SummaryItem 和 BriefingMeta

- **domain** - 删除旧版模型类，清理未用导入
- **__init__** - 更新导出列表

##### 4. 模板空行优化

- **briefing-template** - Jinja2 空格控制语法剔除渲染后多余空行

---

### 2026-05-23 (commit: 2d160f7)，作者：wghlmg1210

#### 研发工程

##### 1. SummaryCluster 归置到 domain.py

- **domain** - 新增 SummaryCluster 模型（从 summarize.py 迁移）

##### 2. Logger 工具化改造

- **logger** - 新增统一日志模块，路径统一为 `output/{date}/run.log`
- **work_module** - 简化基类，移除 `self.log()` 方法
- **llm_client** - 日志改用统一 logger
- **news_frontier、ingest、filter_rank、summarize、assemble** - print 全部替换为 logger

##### 3. 抽象 LarkCommander 命令执行器

- **lark_commander** - 新增 Lark 命令链式调用封装，覆盖 Wiki/Base/Docs/IM
- **publish2lark、publish2lark_base、push2group** - 重构为 LarkCmd 链式调用

##### 4. 提示词元信息简化

- **filter_rank、summarize** - 提示词简化（移除 url/update_time 等冗余字段）

##### 5. .lobster 工作流配置优化

- **run.sh** - 新增环境启动脚本（cd + venv + SSL + exec 透传）

##### 6. 脚本路径调整

- **init_env.sh** - 路径调整至 `scripts/base/`

#### Skill 框架

##### 5. .lobster 工作流配置优化

- **ai-frontier-daily.example.lobster** - 工作流配置优化（SKILL_DIR 环境变量、args.date 全局参数、cleanup step、文件传递）

##### 6. 文档同步

- **PIPELINE.md** - 文档同步更新（补充 cleanup/publish2lark_base 步骤）
- **SKILL.md** - 路径引用更新

---

### 2026-05-21 (commit: -)，作者：wghlmg1210

#### 研发工程

- **filter_rank** - 新增关键词聚类与历史去重
  - 新增 `KeywordClusterer` 类，基于 Jaccard 相似度聚类
  - 新增 `HistoricalKeywordDedup` 类，跨日去重
  - 输出格式从 items 改为 clusters
- **assemble** - 支持新旧格式兼容
  - 新增 `_cluster_to_summary_item()` 方法
  - 支持 clusters 和 items 两种输入格式
- **ingest** - 双层去重策略优化
  - URL 精确匹配 + 标题相似度去重
  - 跨日去重增加多层匹配（URL/标题/内容摘要）
- **config** - 新增关键词去重配置段
  - keyword_dedup.similarity_threshold（聚类阈值）
  - keyword_dedup.recent_days（历史去重天数）
- **domain** - 新增 NewsCluster 数据模型
  - 支持集群合并、关键词管理
  - 包含 merged_relevance、merged_hot_level 等聚合字段

#### 提示词工程

- **filter_ranker.j2.md、summarizer.j2.md** - 提示词命名调整 & 版本升级
  - 新增 `keywords` 字段（2-5个关键词）
  - 定义关键词提取规则和示例

---

### 2026-05-19 (commit: 66cc36f)，作者：wghlmg1210

#### SKILL框架

- **SKILL.md** - 大幅精简重构，Skill 作为标准接口对接 Agent
  - 简化为 7 个章节，聚焦核心流程
  - 新增 Lobster 工作流调用方式
  - 移除复杂的分步执行和排错说明
- **config/secrets.example.json** - 新增 space_id 字段
  - 飞书知识库 Space ID 配置项
- **references/** - 新增工作流定义与说明文档（Skill 标准规范）
  - **ai-frontier-daily.lobster**：定义 4 步工作流（news_frontier → publish2lark → push2group → final_report）
  - **PIPELINE.md**：完整描述工作流步骤、数据流图和目录结构
- **scripts/** - 新增脚本目录（Skill 标准规范）
  - **init_env.sh**：环境检查和初始化脚本
  - **news_frontier.py**：从 project-space/pipeline.py 重命名，作为工作流入口
  - **render_wechat.sh**：微信渲染脚本（从 config/secrets.json 读取配置）
  - **publish2lark.py**：飞书发布脚本（月份归档、同名去重）
  - **push2group.py**：从 postact-space/push_feishu_bot.py 重命名
- **postact-space/POST_PUBLISH.md** - 删除，合并至 references/PIPELINE.md

---

### 2026-05-19 (commit: 1fef247)，作者：Dr-wgylmg1210

#### 研发工程

- **SKILL.md** - 发布后流程重构，引用独立文档
  - 发布后流程拆分至 POST_PUBLISH.md
  - 简化主文档，保留流程概览
- **postact-space/POST_PUBLISH.md** - 新增发布后流程文档
  - 飞书知识库发布（同名去重 + 新建归档）
  - 群机器人 Webhook 推送
  - 从 SKILL.md 拆分独立管理
- **postact-space/push_feishu_bot** - 从 project-space 迁移至 postact-space
  - 调整路径引用（_PROJECT_SPACE → _POSTACT_SPACE）
  - 优化导入结构
- **assemble** - 影响字段重构
  - impact_1/impact_2 → impacts（数组）
  - 更新过滤逻辑和日志输出
- **config** - 配置优化
  - 极客公园源注释（TCP 连接超时）
  - InfoQ 源关闭 SSL 认证
  - default_max_tokens 提升至 81920
- **ingest** - 数据抓取优化
  - 添加 urllib3 禁用 SSL 警告
  - _fetch() 添加连接超时参数（5秒）
  - 添加抓取耗时日志
- **briefing-template** - 模板结构调整
  - 今日速览移至正文前
  - 影响字段改为数组渲染
  - 标签/链接改为引用块样式

#### 提示词工程

- **summarizer.md.j2** - 字段协议更新
  - impact_1/impact_2 → impacts（数组，1～2条）
  - 更新字段验证规则
  - 调整输出示例

---

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

---

### v1.0.0 - 2026-05-11
- 初始化项目结构
- 完成飞书CLI集成
- 实现基本早报流水线（ingest → summarize → assemble）
- 支持飞书文档发布和机器人推送
- 创建 project-space、extension、references 目录
