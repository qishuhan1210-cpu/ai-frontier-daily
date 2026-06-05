import { Page, BrowserContext } from 'playwright';
import { CONFIG, XHS_CONFIG } from './config';

// ============ 微信公众号发布函数 ============

export async function openLocalHtml(page: Page, filePath: string): Promise<void> {
  await page.goto(`file://${filePath}`);
  await page.waitForLoadState('networkidle');
}

export async function copyToClipboard(page: Page, useMeta: boolean = false): Promise<void> {
  const key = useMeta ? 'Meta' : 'Control';
  await page.keyboard.press(`${key}+A`);
  await page.keyboard.press(`${key}+C`);
}

export async function openWechat(page: Page, url: string): Promise<void> {
  await page.goto(url);
  await page.waitForLoadState('networkidle');
}

export async function openEditor(context: BrowserContext, page: Page): Promise<Page> {
  const pagePromise = context.waitForEvent('page');
  const articleBtn = await page.waitForSelector(CONFIG.ARTICLE_BTN_SELECTOR, { timeout: 30000 });
  await articleBtn.click();
  const editorPage = await pagePromise;
  await editorPage.waitForLoadState('networkidle');
  return editorPage;
}

export async function uploadCoverImage(editorPage: Page, imagePath: string): Promise<void> {
  const [fileChooser] = await Promise.all([
    editorPage.waitForEvent('filechooser'),
    editorPage.locator(CONFIG.COVER_UPLOAD_SELECTOR).click(),
  ]);
  await fileChooser.setFiles(imagePath);
  await editorPage.waitForTimeout(1500);
}

export async function fillTitle(editorPage: Page, title: string): Promise<void> {
  const titleInput = await editorPage.waitForSelector(CONFIG.TITLE_SELECTOR, { timeout: 30000 });
  await titleInput.click();
  await editorPage.keyboard.press('Meta+A');
  await editorPage.keyboard.type(title);
}

export async function pasteContent(editorPage: Page, useMeta: boolean = false): Promise<void> {
  const editor = await editorPage.waitForSelector(CONFIG.EDITOR_SELECTOR, { timeout: 30000 });
  await editor.click();
  const key = useMeta ? 'Meta' : 'Control';
  await editorPage.keyboard.press(`${key}+A`);
  await editorPage.keyboard.press(`${key}+V`);
}

export async function saveDraft(editorPage: Page): Promise<void> {
  const saveBtn = await editorPage.waitForSelector(CONFIG.SAVE_DRAFT_SELECTOR, { timeout: 10000 });
  await saveBtn.click();
  try {
    await editorPage.waitForSelector('text=保存成功', { timeout: 10000 });
  } catch {}
}

// ============ 小红书发布函数 ============

export async function navigateToPublish(page: Page): Promise<void> {
  await page.goto(XHS_CONFIG.XHS_URL);
  await page.waitForLoadState('networkidle');
}

export async function switchToImageTab(page: Page): Promise<void> {
  const tab = page.locator(XHS_CONFIG.IMAGE_TAB_SELECTOR);
  if (await tab.count() > 0) {
    await tab.first().click();
    await page.waitForTimeout(500);
  }
}

export async function uploadImages(page: Page, imagePaths: string[]): Promise<void> {
  const [fileChooser] = await Promise.all([
    page.waitForEvent('filechooser'),
    page.locator(XHS_CONFIG.IMAGE_UPLOAD_SELECTOR).first().click(),
  ]);
  await fileChooser.setFiles(imagePaths);
}

export async function waitForUploadComplete(page: Page): Promise<void> {
  try {
    await page.waitForSelector(XHS_CONFIG.UPLOAD_DONE_SELECTOR, { timeout: 5000 });
    await page.waitForSelector(XHS_CONFIG.UPLOAD_DONE_SELECTOR, { state: 'hidden', timeout: 60000 });
  } catch {
    // 进度条未出现（文件瞬间完成），直接继续
  }
  await page.waitForTimeout(1000);
}

export async function fillXhsTitle(page: Page, title: string): Promise<void> {
  const titleInput = await page.waitForSelector(XHS_CONFIG.TITLE_SELECTOR, { timeout: 30000 });
  await titleInput.fill(title);
}

export async function fillXhsContent(page: Page, text: string): Promise<void> {
  const editor = await page.waitForSelector(XHS_CONFIG.EDITOR_SELECTOR, { timeout: 30000 });
  await editor.click();
  await page.keyboard.press('Meta+A');
  await page.keyboard.type(text);
}

export async function publishNote(page: Page): Promise<void> {
  const btn = page.locator(XHS_CONFIG.PUBLISH_BTN_SELECTOR);
  await btn.waitFor({ state: 'visible', timeout: 10000 });
  await page.waitForFunction(
    (selector: string) => {
      const el = document.querySelector(selector) as HTMLButtonElement | null;
      return el && !el.disabled;
    },
    XHS_CONFIG.PUBLISH_BTN_SELECTOR,
    { timeout: 60000 }
  );
  await btn.click();
  await page.waitForTimeout(3000);
}
