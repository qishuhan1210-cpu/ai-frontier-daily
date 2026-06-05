# 微信公众号 & 小红书 Playwright 自动化

## 项目位置

`project-space2/` 目录

## 功能概述

基于 Playwright 实现多平台内容自动发布，当前支持：

- **微信公众号**：本地 HTML → 复制 → 公众号编辑器 → 保存草稿
- **小红书**：本地图片 + 文案 → 图文笔记发布
- **通用**：登录状态保存与跨会话复用（`storageState`）

此外包含独立的小红书卡片批量截图工具（`screenshot-redbook-cdp.ts`），基于 Chrome CDP 实现，不依赖 Playwright。

## 目录结构

```
project-space2/
├── src/
│   ├── main.ts                      # 统一 CLI 入口（commander）
│   └── services/
│       ├── config.ts                # 配置加载器（读取 config/config.yaml）
│       ├── auth.ts                  # AuthService：保存 / 加载登录态
│       ├── publisher.ts             # 微信 & 小红书各步骤函数
│       └── screenshot-redbook-cdp.ts  # 小红书卡片批量截图（CDP 独立实现）
├── config/
│   ├── config.yaml                  # 统一配置（env + wechat + xhs 三段）
│   ├── auth.json                    # 微信登录态（运行后生成）
│   └── xhs-auth.json                # 小红书登录态（运行后生成）
├── package.json
└── tsconfig.json
```

## 配置文件

所有配置集中在 `config/config.yaml` 一个文件中，分三个顶级区块：

| 区块 | 说明 |
|------|------|
| `env` | Chrome 路径、用户数据目录（两个平台共用） |
| `wechat` | 微信公众号的路径、URL、selector、标题模板 |
| `xhs` | 小红书的路径、URL、selector、标题模板 |

## 使用方式

```bash
cd project-space2
npm install
```

### 微信公众号

```bash
# 首次 / 登录态过期：保存登录状态
npm run save-auth
# → 打开 Chrome → 手动扫码登录 → 点击 Resume → 自动保存至 config/auth.json

# 完整发布（默认今日）
npm run publish
npm run publish -- 2026-06-04   # 指定日期
```

发布步骤（自动执行）：
1. 打开 `output/{date}/briefing-wechat.html` 并全选复制
2. 打开微信公众平台，检测登录态（未登录则自动触发 save-auth）
3. 点击「新创作 → 文章」进入编辑器
4. 填入文章标题（模板：`AI 前沿早报（{date}）`）
5. 粘贴正文
6. 保存为草稿

### 小红书

```bash
# 首次 / 登录态过期：保存登录状态
npm run xhs-save-auth

# 发布图文笔记（默认今日）
npm run xhs-publish
npm run xhs-publish -- 2026-06-04   # 指定日期
```

所需输入文件：
- `output/{date}/redbook-png/*.png`：图片文件（按文件名排序上传）
- `output/{date}/briefing-xhs-text.txt`：正文文案

发布步骤（自动执行）：
1. 导航到小红书创作者发布页，检测登录态
2. 切换到「发布图文」Tab
3. 上传图片，等待上传完成
4. 填入标题和正文
5. 点击「发布笔记」

### 小红书卡片批量截图

独立脚本，不走 `main.ts` 入口，直接用 `tsx` 运行：

```bash
npx tsx src/services/screenshot-redbook-cdp.ts [date]
```

- 输入：`output/{date}/redbook/*.html`
- 输出：`output/{date}/redbook-png/*.png`（2x 分辨率）
- 基于 Chrome CDP 实现，无 Playwright 依赖，headless 运行

### 查看所有命令

```bash
npm run wechat-mp -- --help
```

## 登录方案说明

- 使用 Playwright `storageState`（Cookie + localStorage）保存登录态
- 登录态文件：微信 `config/auth.json`，小红书 `config/xhs-auth.json`
- 使用系统已安装的 Chrome（`channel: 'chrome'`），非 Playwright 内置浏览器
- `publish` / `xhs-publish` 命令内置登录态检测：若未登录自动触发 `saveAuth()` 再继续
- 登录态随平台 Session 过期失效，届时重新运行对应的 `save-auth` 命令

## 注意事项

- 运行超时保护：单次流程超过 10 分钟自动退出
- 封面图上传功能已实现（`uploadCoverImage`）但当前在 `publish` 流程中注释掉
- 截图工具日志写入 `output/{date}/run.log`
