import { chromium, Browser, BrowserContext, Page, BrowserContextOptions } from 'playwright';
import { CONFIG } from './config';
import * as fs from 'fs';
import * as path from 'path';

export interface AuthServiceConfig {
  loginUrl?: string;
  authFile?: string;
  chromeChannel?: string;
}

export class AuthService {
  private config: AuthServiceConfig;

  constructor(config: AuthServiceConfig = {}) {
    this.config = {
      loginUrl: config.loginUrl || CONFIG.WECHAT_URL,
      authFile: config.authFile || CONFIG.AUTH_FILE,
      chromeChannel: config.chromeChannel || 'chrome',
    };
  }

  async saveAuth(): Promise<void> {
    const browser = await chromium.launch({
      headless: false,
      channel: this.config.chromeChannel as any,
    });
    const context = await browser.newContext();
    const page = await context.newPage();

    console.log(`导航到登录页面: ${this.config.loginUrl}`);
    await page.goto(this.config.loginUrl!);

    console.log('请在弹出的浏览器窗口中完成微信公众号登录...');
    console.log('登录完成后，请在浏览器中按下 "Resume" 按钮继续');
    
    await page.pause();

    console.log(`保存登录状态到: ${this.config.authFile}`);
    await context.storageState({ path: this.config.authFile! });

    console.log('登录状态保存成功！');
    await browser.close();
  }

  async loadAuth(): Promise<{ browser: Browser; context: BrowserContext; page: Page }> {
    if (!fs.existsSync(this.config.authFile!)) {
      throw new Error(`未找到登录状态文件 ${this.config.authFile}，请先运行 saveAuth()`);
    }

    const contextOptions: BrowserContextOptions = {
      storageState: this.config.authFile,
    };

    const browser = await chromium.launch({
      headless: false,
      channel: this.config.chromeChannel as any,
    });
    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();

    return { browser, context, page };
  }
}
