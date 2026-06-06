import { AuthService } from './auth';
import { CONFIG } from './config';
import { WechatActions } from './actions';
import * as fs from 'fs';
import * as path from 'path';

/**
 * 微信公众号业务流程层
 * 编排完整的发布流程
 */
export class WechatPublisher {
  private authService: AuthService;
  private browser?: import('playwright').Browser;
  private context?: import('playwright').BrowserContext;
  private mainPage?: import('playwright').Page;
  private editorPage?: import('playwright').Page;
  
  // 维护多个 WechatActions 实例，对应不同的页面
  private mainActions?: WechatActions;
  private editorActions?: WechatActions;

  private date: string;
  private htmlPath: string;
  private title: string;

  constructor(date?: string) {
    this.authService = new AuthService();
    this.date = date || new Date().toISOString().slice(0, 10);
    this.title = CONFIG.ARTICLE_TITLE_TEMPLATE.replace('{date}', this.date);
    this.htmlPath = path.resolve(CONFIG.BASE_DIR, this.date, CONFIG.HTML_FILENAME);

    if (!fs.existsSync(this.htmlPath)) {
      console.error(`❌ 文件不存在: ${this.htmlPath}`);
      process.exit(1);
    }
  }

  async saveAuth(): Promise<void> {
    try {
      await this.authService.saveAuth();
    } catch (error) {
      console.error('登录失败:', (error as Error).message);
      process.exit(1);
    }
  }

  private async initBrowser(): Promise<void> {
    ({ browser: this.browser, context: this.context, page: this.mainPage } = 
      await this.authService.loadAuth());
    this.mainActions = new WechatActions(this.mainPage!, this.context!);
  }

  private async copyHtmlContent(): Promise<void> {
    console.log('\n🚀 步骤1: 打开本地 HTML 并复制内容');
    await this.mainActions!.openAndCopyHtml(this.htmlPath);
    console.log('   ✓ 已全选复制页面内容');
  }

  private async openWechatPlatform(): Promise<void> {
    console.log('\n🚀 步骤2: 打开微信公众平台');
    await this.mainActions!.openPlatform();
    
    const isLoggedIn = await this.mainActions!.checkLogin();
    if (!isLoggedIn) {
      console.log('   ⚠️  未检测到登录状态，启动登录流程...');
      await this.browser!.close();
      await this.authService.saveAuth();
      await this.initBrowser();
      await this.mainActions!.openPlatform();
    }
    console.log('   ✓ 已打开微信公众平台');
  }

  private async editArticle(): Promise<void> {
    console.log('\n🚀 步骤3: 进入文章编辑器');
    this.editorPage = await this.mainActions!.openEditor();
    this.editorActions = new WechatActions(this.editorPage);
    console.log('   ✓ 编辑器页面已打开');
  }

  private async fillArticleContent(): Promise<void> {
    console.log('\n🚀 步骤5: 填入文章标题');
    await this.editorActions!.fillTitle(this.editorPage!, this.title);
    console.log(`   ✓ 标题已填入: ${this.title}`);

    console.log('\n🚀 步骤6: 粘贴正文到编辑器');
    await this.editorActions!.pasteContent(this.editorPage!);
    console.log('   ✓ 已粘贴正文');

    console.log('\n🚀 步骤7: 保存草稿');
    await this.editorActions!.saveDraft(this.editorPage!);
    console.log('   ✓ 草稿保存成功！');
  }

  async publish(): Promise<void> {
    console.log(`📁 日期: ${this.date}`);
    console.log(`📁 HTML路径: ${this.htmlPath}`);

    try {
      await this.initBrowser();
      await this.copyHtmlContent();
      await this.openWechatPlatform();
      
      await this.editArticle();
      await this.fillArticleContent();

      console.log('\n🎉 自动化流程完成！');
    } catch (error) {
      console.error('\n❌ 发布失败:', (error as Error).message);
      throw error;
    } finally {
      await this.browser?.close();
    }
  }
}