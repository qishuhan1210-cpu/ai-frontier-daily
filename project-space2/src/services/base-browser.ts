import { Page, BrowserContext } from 'playwright';

/**
 * 浏览器操作基类
 * 提供通用的浏览器操作方法
 */
export class BaseBrowserOps {
  constructor(protected page: Page, protected context?: BrowserContext) {}

  async navigateTo(url: string): Promise<void> {
    await this.page.goto(url);
    try {
      await this.page.waitForLoadState('networkidle', { timeout: 10000 });
    } catch {
      await this.page.waitForLoadState('load');
    }
  }

  async openLocalFile(filePath: string): Promise<void> {
    await this.page.goto(`file://${filePath}`);
    await this.page.waitForLoadState('networkidle');
  }

  protected isMacOS(): boolean {
    return process.platform === 'darwin';
  }

  async selectAllAndCopy(): Promise<void> {
    const key = this.isMacOS() ? 'Meta' : 'Control';
    await this.page.keyboard.press(`${key}+A`);
    await this.page.keyboard.press(`${key}+C`);
  }

  async selectAllAndPaste(): Promise<void> {
    const key = this.isMacOS() ? 'Meta' : 'Control';
    await this.page.keyboard.press(`${key}+A`);
    await this.page.keyboard.press(`${key}+V`);
  }

  async clickElement(selector: string, timeout: number = 30000): Promise<void> {
    const element = await this.page.waitForSelector(selector, { timeout });
    await element.click();
  }

  async hasElement(selector: string): Promise<boolean> {
    const element = await this.page.$(selector);
    return element !== null;
  }

  async wait(ms: number): Promise<void> {
    await this.page.waitForTimeout(ms);
  }

  async pressKey(key: string): Promise<void> {
    await this.page.keyboard.press(key);
  }

  async jsClick(selector: string): Promise<void> {
    await this.page.$eval(selector, (el: HTMLElement) => el.click());
  }

  async pierceClick(hostSelector: string, innerSelector: string): Promise<void> {
    const host = this.page.locator(hostSelector);
    await host.locator(innerSelector).click();
  }
}

/**
 * 微信浏览器操作类
 */
export class WechatBrowserOps extends BaseBrowserOps {
  /**
   * 点击按钮并等待新页面打开（同时触发，避免竞态）
   */
  async clickAndWaitForNewPage(selector: string): Promise<Page> {
    if (!this.context) {
      throw new Error('BrowserContext is required');
    }
    const [newPage] = await Promise.all([
      this.context.waitForEvent('page'),
      this.clickElement(selector),
    ]);
    return newPage;
  }

  async typeInInput(selector: string, text: string, timeout: number = 30000): Promise<void> {
    const input = await this.page.waitForSelector(selector, { timeout });
    await input.click();
    const key = this.isMacOS() ? 'Meta' : 'Control';
    await this.page.keyboard.press(`${key}+A`);
    await this.page.keyboard.type(text);
  }

  async uploadFile(selector: string, filePath: string): Promise<void> {
    const [fileChooser] = await Promise.all([
      this.page.waitForEvent('filechooser'),
      this.page.locator(selector).click(),
    ]);
    await fileChooser.setFiles(filePath);
    await this.page.waitForTimeout(1500);
  }

  async waitForText(text: string, timeout: number = 10000): Promise<void> {
    await this.page.waitForSelector(`text=${text}`, { timeout });
  }
}

/**
 * 小红书浏览器操作类
 */
export class XhsBrowserOps extends BaseBrowserOps {
  async clickVisible(selector: string): Promise<void> {
    await this.page.locator(selector).click();
  }

  async fillInput(selector: string, text: string, timeout: number = 30000): Promise<void> {
    const input = await this.page.waitForSelector(selector, { timeout });
    await input.fill(text);
  }

  async fillDatetimeInput(selector: string, datetime: string): Promise<void> {
    const input = await this.page.waitForSelector(selector, { timeout: 10000 });
    await input.click({ clickCount: 3 });
    await input.fill(datetime);
    await this.page.keyboard.press('Enter');
  }

  async clickAndType(selector: string, text: string, timeout: number = 30000): Promise<void> {
    const element = await this.page.waitForSelector(selector, { timeout });
    await element.click();
    const key = this.isMacOS() ? 'Meta' : 'Control';
    await this.page.keyboard.press(`${key}+A`);
    await this.page.keyboard.type(text);
  }

  async typeInEditor(selector: string, text: string, timeout: number = 30000): Promise<void> {
    const element = await this.page.waitForSelector(selector, { timeout });
    await element.click();
    await this.page.keyboard.press('End');
    await this.page.keyboard.type(text);
  }

  async uploadImages(selector: string, imagePaths: string[]): Promise<void> {
    const [fileChooser] = await Promise.all([
      this.page.waitForEvent('filechooser'),
      this.page.locator(selector).first().click(),
    ]);
    await fileChooser.setFiles(imagePaths);
  }

  async waitForElement(selector: string, timeout: number = 5000): Promise<void> {
    await this.page.waitForSelector(selector, { timeout });
  }

  async waitForElementHidden(selector: string, timeout: number = 60000): Promise<void> {
    await this.page.waitForSelector(selector, { state: 'hidden', timeout });
  }

  async waitForButtonEnabled(selector: string, timeout: number = 60000): Promise<void> {
    await this.page.waitForFunction(
      (sel: string) => {
        const el = document.querySelector(sel) as HTMLButtonElement | null;
        return el && !el.disabled;
      },
      selector,
      { timeout }
    );
  }

  // xhs-publish-btn 是 Vue Web Component，内部按钮不在标准 DOM 里。
  // 通过元素 boundingBox 定位后点击右侧红色"定时发布"/"发布"按钮区域。
  async clickPublishBtn(): Promise<void> {
    // 先按 Escape 关闭可能打开的日历等弹窗
    await this.page.keyboard.press('Escape');
    await this.page.waitForTimeout(300);

    const host = this.page.locator('xhs-publish-btn');
    await host.waitFor({ state: 'attached', timeout: 10000 });
    const box = await host.boundingBox();
    if (!box) throw new Error('xhs-publish-btn boundingBox 为空，元素不可见');

    // 右侧约 2/3 处是红色发布按钮，左侧 1/3 是"暂存离开"
    const x = box.x + box.width * 0.75;
    const y = box.y + box.height / 2;
    await this.page.mouse.click(x, y);
  }

  async waitForVisible(selector: string, timeout: number = 10000): Promise<void> {
    await this.page.locator(selector).waitFor({ state: 'visible', timeout });
  }

  async getElementCount(selector: string): Promise<number> {
    return await this.page.locator(selector).count();
  }
}
