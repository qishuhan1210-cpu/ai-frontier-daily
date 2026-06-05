# 微信公众号浏览器自动化

基于 Playwright 的微信公众号页面自动化工具，支持操作已登录页面和内容发布。

## 功能特性

- ✅ 保存登录状态（Cookie + localStorage）
- ✅ 复用登录状态，无需重复登录
- ✅ 使用系统已安装的 Chrome 浏览器
- ✅ 支持微信公众号等需要登录的页面
- ✅ 打开并复制本地 HTML 内容到剪贴板
- ✅ 完整的自动化发布流程：从 HTML 到微信公众号草稿

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 安装 Playwright 浏览器（首次使用）

```bash
npm run install-browsers
```

### 3. 保存登录状态（首次使用或登录态过期时）

```bash
npm run save-auth
```

执行后：
- 会打开 Chrome 浏览器并导航到微信公众号登录页
- 在浏览器中手动完成登录（扫码或账号密码登录）
- 登录完成后，点击浏览器中的 "Resume" 按钮
- 登录状态会自动保存到 `config/auth.json` 文件

### 4. 查看可用命令

```bash
npm run wechat-mp -- --help
```

### 5. 常用命令

#### 复用登录状态（仅打开微信公众号）

```bash
npm run use-auth
```

执行后：
- 会加载之前保存的 `auth.json` 登录状态
- 打开已登录状态的浏览器
- 直接导航到微信公众号页面

#### 复制本地 HTML 内容到剪贴板

```bash
npm run copy-html
# 或指定日期
npm run copy-html 2026-06-04
```

执行后：
- 会打开指定日期的 HTML 文件
- 自动全选并复制内容到剪贴板

#### 完整发布流程

```bash
npm run publish
# 或指定日期
npm run publish 2026-06-04
```

执行后会自动完成以下步骤：
1. 打开本地 HTML 并复制内容
2. 打开微信公众平台
3. 进入文章编辑器
4. 粘贴内容到编辑器
5. 保存为草稿

## 文件结构

```
├── src/
│   ├── index.ts          # 统一入口脚本，提供 CLI 命令
│   ├── config.ts         # 配置加载器
│   └── services/
│       ├── auth.ts       # 认证服务（保存/加载登录态）
│       └── publisher.ts  # 发布服务（HTML 复制、内容粘贴等）
├── config/
│   ├── config.json       # 主配置文件
│   └── auth.json         # 登录状态文件（运行后生成）
├── package.json          # 项目配置
├── package-lock.json     # 依赖锁定文件
├── tsconfig.json         # TypeScript 配置
└── README.md             # 使用说明
```

## 配置说明

编辑 `config/config.json` 文件修改配置：

```json
{
  "LOGIN_URL": "https://mp.weixin.qq.com",
  "TARGET_URL": "https://mp.weixin.qq.com",
  "AUTH_FILE": "config/auth.json",
  "BASE_DIR": "../output",
  "WECHAT_URL": "https://mp.weixin.qq.com",
  "CHROME_PATH": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "USER_DATA_DIR": "~/Library/Application Support/Google/Chrome"
}
```

配置项说明：
- `LOGIN_URL`: 登录页面地址
- `TARGET_URL`: 目标页面地址
- `AUTH_FILE`: 登录状态保存的文件路径
- `BASE_DIR`: HTML 文件所在的基础目录
- `WECHAT_URL`: 微信公众平台地址
- `CHROME_PATH`: Chrome 浏览器路径
- `USER_DATA_DIR`: Chrome 用户数据目录

## 技术原理

### 登录状态保存

```typescript
// src/services/auth.ts
async saveAuth(): Promise<void> {
  const browser = await chromium.launch({
    headless: false,
    channel: 'chrome',
  });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(LOGIN_URL);
  await page.pause(); // 等待手动登录
  await context.storageState({ path: authFile }); // 保存登录态
}
```

### 登录状态复用

```typescript
// src/services/auth.ts
async loadAuth(): Promise<{ browser: Browser; context: BrowserContext; page: Page }> {
  const context = await browser.newContext({
    storageState: authFile, // 加载登录态
  });
  const page = await context.newPage();
  return { browser, context, page };
}
```

### 自动化发布流程

```typescript
// src/index.ts - publish 命令
1. 打开本地 HTML 并复制内容
2. 打开微信公众平台
3. 进入文章编辑器
4. 粘贴内容到编辑器
5. 保存为草稿
```

## 注意事项

1. **Node.js 版本要求**: >= 18.0.0
2. **浏览器要求**: 需要安装 Google Chrome 浏览器
3. **登录态有效期**: 登录态会随网站 Session 过期而失效，届时需重新运行 `npm run save-auth`
4. **HTML 文件位置**: 默认从 `../output/[日期]/briefing-wechat.html` 读取
5. **跨设备迁移**: 复制整个目录即可迁移，`config/auth.json` 包含完整登录状态

## 故障排除

### Q: 浏览器无法启动？
A: 确保已安装 Google Chrome 浏览器，或修改脚本使用其他浏览器。

### Q: 登录后状态未保存？
A: 确保登录完成后点击了 "Resume" 按钮，检查是否有错误输出。

### Q: 复用登录态后仍未登录？
A: 检查 `config/auth.json` 文件是否存在，登录态可能已过期，需重新保存。

### Q: HTML 文件找不到？
A: 确保 `config/config.json` 中的 `BASE_DIR` 配置正确，并且指定日期的 HTML 文件存在。

## License

MIT
