import { Page, BrowserContext } from 'playwright';
import { WechatBrowserOps, XhsBrowserOps } from './base-browser';
import { CONFIG, XHS_CONFIG } from './config';

/**
 * 微信公众号业务语义层
 * 将浏览器操作组合成具有业务含义的操作
 */
export class WechatActions {
  private browserOps: WechatBrowserOps;

  constructor(private page: Page, private context?: BrowserContext) {
    this.browserOps = new WechatBrowserOps(page, context);
  }

  async openAndCopyHtml(filePath: string): Promise<void> {
    await this.browserOps.openLocalFile(filePath);
    await this.browserOps.selectAllAndCopy();
  }

  async openPlatform(): Promise<void> {
    await this.browserOps.navigateTo(CONFIG.WECHAT_URL);
  }

  async checkLogin(): Promise<boolean> {
    return await this.browserOps.hasElement(CONFIG.LOGIN_CHECK_SELECTOR);
  }

  async openEditor(): Promise<Page> {
    const editorPage = await this.browserOps.clickAndWaitForNewPage(CONFIG.ARTICLE_BTN_SELECTOR);
    await editorPage.waitForLoadState('networkidle');
    return editorPage;
  }

  async fillTitle(editorPage: Page, title: string): Promise<void> {
    const ops = new WechatBrowserOps(editorPage);
    await ops.typeInInput(CONFIG.TITLE_SELECTOR, title);
  }

  async pasteContent(editorPage: Page): Promise<void> {
    const ops = new WechatBrowserOps(editorPage);
    await ops.clickElement(CONFIG.EDITOR_SELECTOR);
    await ops.selectAllAndPaste();
  }

  async saveDraft(editorPage: Page): Promise<void> {
    const ops = new WechatBrowserOps(editorPage);
    await ops.clickElement(CONFIG.SAVE_DRAFT_SELECTOR, 10000);
    try {
      await ops.waitForText('保存成功', 10000);
    } catch {}
  }
}

/**
 * 小红书业务语义层
 * 将浏览器操作组合成具有业务含义的操作
 */
export class XhsActions {
  private browserOps: XhsBrowserOps;

  constructor(private page: Page) {
    this.browserOps = new XhsBrowserOps(page);
  }

  async openPublishPage(): Promise<void> {
    await this.browserOps.navigateTo(XHS_CONFIG.XHS_URL);
  }

  async checkLogin(): Promise<boolean> {
    return await this.browserOps.hasElement(XHS_CONFIG.LOGIN_CHECK_SELECTOR);
  }

  async switchToImageTab(): Promise<void> {
    await this.browserOps.clickVisible(XHS_CONFIG.IMAGE_TAB_SELECTOR);
    await this.browserOps.wait(500);
  }

  async uploadImages(imagePaths: string[]): Promise<void> {
    await this.browserOps.uploadImages(XHS_CONFIG.IMAGE_UPLOAD_SELECTOR, imagePaths);
  }

  async fillTitle(title: string): Promise<void> {
    await this.browserOps.fillInput(XHS_CONFIG.TITLE_SELECTOR, title);
  }

  async fillContent(text: string): Promise<void> {
    await this.browserOps.clickAndType(XHS_CONFIG.EDITOR_SELECTOR, text);
  }

  async selectTags(tags: string[]): Promise<void> {
    for (const tag of tags) {
      await this.browserOps.typeInEditor(XHS_CONFIG.EDITOR_SELECTOR, `#${tag}`);
      try {
        await this.browserOps.waitForElement(`.tag:has-text("${tag}")`, 3000);
        await this.browserOps.clickElement(`.tag:has-text("${tag}")`);
      } catch {
        // 未找到标签建议，按 Escape 关闭下拉并跳过
        await this.browserOps.pressKey('Escape');
      }
      await this.browserOps.wait(300);
    }
  }

  async setScheduledPublish(datetime: string): Promise<void> {
    // 通过 JS 点击 checkbox，绕过可见性限制
    await this.browserOps.jsClick(XHS_CONFIG.SCHEDULE_SWITCH_SELECTOR);
    await this.browserOps.wait(500);
    // 清空并填入日期时间
    await this.browserOps.fillDatetimeInput(XHS_CONFIG.SCHEDULE_DATETIME_SELECTOR, datetime);
    await this.browserOps.wait(300);
  }

 async publish(): Promise<void> {
    // xhs-publish-btn 是 Vue 自定义组件，内部按钮不在标准 DOM 中，
    // 改用 boundingBox 定位后点击右侧"定时发布"/"发布"红色按钮区域
    await this.browserOps.clickPublishBtn();
    await this.browserOps.wait(3000);
  }
}
