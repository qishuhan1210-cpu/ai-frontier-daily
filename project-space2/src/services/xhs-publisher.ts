import { AuthService } from './auth';
import { XHS_CONFIG } from './config';
import { XhsActions } from './actions';
import * as fs from 'fs';
import * as path from 'path';

export class XhsPublisher {
  private authService: AuthService;
  private browser?: import('playwright').Browser;
  private page?: import('playwright').Page;
  private actions?: XhsActions;

  private date: string;
  private imagesDir: string;
  private title: string;
  private imagePaths: string[] = [];
  private textContent: string = '';

  constructor(date?: string) {
    this.authService = new AuthService({
      loginUrl: XHS_CONFIG.XHS_URL,
      authFile: XHS_CONFIG.XHS_AUTH_FILE,
    });
    this.date = date || new Date().toISOString().slice(0, 10);
    this.imagesDir = path.resolve(XHS_CONFIG.BASE_DIR, this.date, XHS_CONFIG.IMAGES_DIR_NAME);
    this.title = XHS_CONFIG.ARTICLE_TITLE_TEMPLATE.replace('{date}', this.date);

    this.textContent = this.loadTextContent();
    this.imagePaths = this.loadImagePaths();
  }

  private loadTextContent(): string {
    const summaryFile = path.resolve(XHS_CONFIG.BASE_DIR, this.date, 'summary.json');
    if (!fs.existsSync(summaryFile)) {
      console.error(`❌ summary.json 不存在: ${summaryFile}`);
      process.exit(1);
    }

    const summary = JSON.parse(fs.readFileSync(summaryFile, 'utf-8'));
    const footer = summary?.blocks?.footer as Record<string, string> | undefined;
    if (!footer) {
      console.error('❌ summary.json 中缺少 blocks.footer 字段');
      process.exit(1);
    }

    const sectionNames: Record<string, string> = {
      foundation: '🔧 AI 基石与算力',
      core_tech:  '🧠 大模型与核心技术',
      agent:      '🤖 AI 智能体与交互',
      vertical:   '🏭 AI+ 垂直应用',
      industry:   '🌐 AI 产业与观察',
    };

    return '🚀 今日速览（一句话版）\n\n' + Object.entries(sectionNames)
      .filter(([key]) => footer[key])
      .map(([key, name]) => `${name}\n${footer[key]}`)
      .join('\n\n');
  }

  private loadImagePaths(): string[] {
    if (!fs.existsSync(this.imagesDir)) {
      console.error(`❌ 图片目录不存在: ${this.imagesDir}`);
      process.exit(1);
    }

    const images = fs.readdirSync(this.imagesDir)
      .filter(f => /\.(png|jpg|jpeg|webp|gif)$/i.test(f))
      .sort()
      .map(f => path.join(this.imagesDir, f));

    const quickViewImages = images.filter(f => f.includes('quick-view'));
    const cardImages = images.filter(f => f.includes('card-')).sort((a, b) => {
      const num = (s: string) => { const m = s.match(/card-(\d+)/); return m ? parseInt(m[1], 10) : 0; };
      return num(a) - num(b);
    });

    const result = quickViewImages.concat(cardImages);
    if (result.length === 0) {
      console.error(`❌ 图片目录中没有图片文件: ${this.imagesDir}`);
      process.exit(1);
    }

    return result;
  }

  private shouldSchedule(): boolean {
    const [hour, minute] = XHS_CONFIG.SCHEDULE_TIME.split(':').map(Number);
    const scheduled = new Date(`${this.date}T${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}:00`);
    return new Date() < scheduled;
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
    ({ browser: this.browser, page: this.page } = await this.authService.loadAuth());
    this.actions = new XhsActions(this.page!);
  }

  private async openPublishPage(): Promise<void> {
    console.log('\n🚀 步骤1: 导航到小红书发布页');
    await this.actions!.openPublishPage();

    const isLoggedIn = await this.actions!.checkLogin();
    if (!isLoggedIn) {
      console.log('   ⚠️  未检测到登录状态，启动登录流程...');
      await this.browser!.close();
      await this.authService.saveAuth();
      await this.initBrowser();
      await this.actions!.openPublishPage();
    }
    console.log('   ✓ 已打开小红书发布页');
  }

  private async uploadImages(): Promise<void> {
    console.log('\n🚀 步骤2: 切换到图文 Tab');
    await this.actions!.switchToImageTab();
    console.log('   ✓ 已切换到图文 Tab');

    console.log('\n🚀 步骤3: 上传图片');
    await this.actions!.uploadImages(this.imagePaths);
    console.log('   ✓ 图片上传中...');

    console.log('\n🚀 步骤4: 等待图片上传完成');
    await new Promise(resolve => setTimeout(resolve, 5000));
    console.log('   ✓ 图片上传完成');
  }

  private async fillNoteContent(): Promise<void> {
    console.log('\n🚀 步骤5: 填入标题');
    await this.actions!.fillTitle(this.title);
    console.log(`   ✓ 标题已填入: ${this.title}`);

    console.log('\n🚀 步骤6: 填入正文');
    await this.actions!.fillContent(this.textContent);
    console.log('   ✓ 正文已填入');

    // console.log('\n🚀 步骤7: 选中标签');
    // await this.actions!.selectTags(XHS_CONFIG.TAGS);
    // console.log(`   ✓ 标签已选中: ${XHS_CONFIG.TAGS.join(', ')}`);
  }

  async publish(): Promise<void> {
    console.log(`📁 日期: ${this.date}`);
    console.log(`📸 图片数量: ${this.imagePaths.length}`);
    console.log(`📝 标题: ${this.title}`);

    try {
      await this.initBrowser();
      await this.openPublishPage();
      await this.uploadImages();
      await this.fillNoteContent();

      const useSchedule = this.shouldSchedule();
      if (useSchedule) {
        console.log('\n🚀 步骤8: 配置定时发布');
        const scheduledDatetime = `${this.date} ${XHS_CONFIG.SCHEDULE_TIME}`;
        await this.actions!.setScheduledPublish(scheduledDatetime);
        console.log(`   ✓ 定时发布已设置: ${scheduledDatetime}`);
      } else {
        console.log('\n🚀 步骤8: 跳过定时发布（当前时间已超过定时时间，直接发布）');
      }

      console.log('\n🚀 步骤9: 发布笔记');
      await this.actions!.publish();
      console.log('   ✓ 笔记发布成功！');

      console.log('\n🎉 小红书自动化流程完成！');
    } catch (error) {
      console.error('\n❌ 发布失败:', (error as Error).message);
      throw error;
    } finally {
      await this.browser?.close();
    }
  }
}
