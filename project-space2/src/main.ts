#!/usr/bin/env node

import { Command } from 'commander';
import { AuthService } from './services/auth';
import { CONFIG, XHS_CONFIG } from './services/config';
import * as fs from 'fs';
import * as path from 'path';
import {
  openLocalHtml, copyToClipboard, openWechat,
  openEditor, uploadCoverImage, fillTitle, pasteContent, saveDraft,
  navigateToPublish, switchToImageTab, uploadImages,
  waitForUploadComplete, fillXhsTitle, fillXhsContent, publishNote,
} from './services/publisher';

const MAX_TIMEOUT_MS = 10 * 60 * 1000;
const program = new Command();

function getToday(): string {
  return new Date().toISOString().slice(0, 10);
}

function getHtmlPath(date: string): string {
  return path.resolve(CONFIG.BASE_DIR, date, CONFIG.HTML_FILENAME);
}

function isMacOS(): boolean {
  return process.platform === 'darwin';
}

function formatTitle(date: string): string {
  return CONFIG.ARTICLE_TITLE_TEMPLATE.replace('{date}', date);
}

program
  .name('wechat-mp')
  .description('微信公众号自动化工具')
  .version('1.0.0');

program
  .command('save-auth')
  .description('引导用户授权登录')
  .action(async () => {
    try {
      const authService = new AuthService();
      await authService.saveAuth();
    } catch (error) {
      console.error('登录失败:', (error as Error).message);
      process.exit(1);
    }
  });

program
  .command('publish [date]')
  .description('完整发布流程：复制 HTML → 打开微信 → 进入编辑器 → 填标题 → 粘贴正文 → 保存草稿')
  .action(async (date?: string) => {
    const targetDate = date || getToday();
    const htmlPath = getHtmlPath(targetDate);
    const title = formatTitle(targetDate);

    console.log(`📁 日期: ${targetDate}`);
    console.log(`📁 HTML路径: ${htmlPath}`);

    if (!fs.existsSync(htmlPath)) {
      console.error(`❌ 文件不存在: ${htmlPath}`);
      process.exit(1);
    }

    const timeout = setTimeout(() => {
      console.error('\n⏱️ 运行超时10分钟，强制退出');
      process.exit(1);
    }, MAX_TIMEOUT_MS);
    timeout.unref();

    const authService = new AuthService();
    let browser: import('playwright').Browser | undefined;
    let context: import('playwright').BrowserContext | undefined;
    let page: import('playwright').Page | undefined;

    try {
      ({ browser, context, page } = await authService.loadAuth());

      console.log('\n🚀 步骤1: 打开本地 HTML 并复制内容');
      await openLocalHtml(page!, htmlPath);
      await copyToClipboard(page!, isMacOS());
      console.log('   ✓ 已全选复制页面内容');

      console.log('\n🚀 步骤2: 打开微信公众平台');
      await openWechat(page!, CONFIG.WECHAT_URL);
      const isLoggedIn = await page!.$(CONFIG.LOGIN_CHECK_SELECTOR);

      if (!isLoggedIn) {
        console.log('   ⚠️  未检测到登录状态，启动登录流程...');
        await browser!.close();
        await authService.saveAuth();
        ({ browser, context, page } = await authService.loadAuth());
        await openWechat(page!, CONFIG.WECHAT_URL);
      }
      console.log('   ✓ 已打开微信公众平台');

      console.log('\n🚀 步骤3: 进入文章编辑器');
      const editorPage = await openEditor(context!, page!);
      console.log('   ✓ 编辑器页面已打开');

      // console.log('\n🚀 步骤4: 上传封面图');
      // await uploadCoverImage(editorPage, CONFIG.COVER_IMAGE);
      // console.log('   ✓ 封面图已上传');

      console.log('\n🚀 步骤5: 填入文章标题');
      await fillTitle(editorPage, title);
      console.log(`   ✓ 标题已填入: ${title}`);

      console.log('\n🚀 步骤6: 粘贴正文到编辑器');
      await pasteContent(editorPage, isMacOS());
      console.log('   ✓ 已粘贴正文');

      console.log('\n🚀 步骤7: 保存草稿');
      await saveDraft(editorPage);
      console.log('   ✓ 草稿保存成功！');

      console.log('\n🎉 自动化流程完成！');
    } catch (error) {
      console.error('\n❌ 发布失败:', (error as Error).message);
    } finally {
      clearTimeout(timeout);
      await browser?.close();
      process.exit(0);
    }
  });

program
  .command('xhs-save-auth')
  .description('引导用户授权登录小红书')
  .action(async () => {
    try {
      const authService = new AuthService({
        loginUrl: XHS_CONFIG.XHS_URL,
        authFile: XHS_CONFIG.XHS_AUTH_FILE,
      });
      await authService.saveAuth();
    } catch (error) {
      console.error('登录失败:', (error as Error).message);
      process.exit(1);
    }
  });

program
  .command('xhs-publish [date]')
  .description('发布小红书图文笔记：上传图片 → 填标题 → 填正文 → 发布')
  .action(async (date?: string) => {
    const targetDate = date || getToday();
    const imagesDir = path.resolve(XHS_CONFIG.BASE_DIR, targetDate, XHS_CONFIG.IMAGES_DIR_NAME);
    const textFile = path.resolve(XHS_CONFIG.BASE_DIR, targetDate, XHS_CONFIG.TEXT_FILENAME);
    const title = XHS_CONFIG.ARTICLE_TITLE_TEMPLATE.replace('{date}', targetDate);

    console.log(`📁 日期: ${targetDate}`);

    if (!fs.existsSync(imagesDir)) {
      console.error(`❌ 图片目录不存在: ${imagesDir}`);
      process.exit(1);
    }
    if (!fs.existsSync(textFile)) {
      console.error(`❌ 文本文件不存在: ${textFile}`);
      process.exit(1);
    }

    const imagePaths = fs.readdirSync(imagesDir)
      .filter(f => /\.(png|jpg|jpeg|webp|gif)$/i.test(f))
      .sort()
      .map(f => path.join(imagesDir, f));

    if (imagePaths.length === 0) {
      console.error(`❌ 图片目录中没有图片文件: ${imagesDir}`);
      process.exit(1);
    }

    const textContent = fs.readFileSync(textFile, 'utf-8').trim();

    console.log(`📸 图片数量: ${imagePaths.length}`);
    console.log(`📝 标题: ${title}`);

    const timeout = setTimeout(() => {
      console.error('\n⏱️ 运行超时10分钟，强制退出');
      process.exit(1);
    }, MAX_TIMEOUT_MS);
    timeout.unref();

    const authService = new AuthService({
      loginUrl: XHS_CONFIG.XHS_URL,
      authFile: XHS_CONFIG.XHS_AUTH_FILE,
    });
    let browser: import('playwright').Browser | undefined;
    let page: import('playwright').Page | undefined;

    try {
      ({ browser, page } = await authService.loadAuth());

      console.log('\n🚀 步骤1: 导航到小红书发布页');
      await navigateToPublish(page!);

      // 登录态检测
      const isLoggedIn = await page!.$(XHS_CONFIG.LOGIN_CHECK_SELECTOR);
      if (!isLoggedIn) {
        console.log('   ⚠️  未检测到登录状态，启动登录流程...');
        await browser!.close();
        await authService.saveAuth();
        ({ browser, page } = await authService.loadAuth());
        await navigateToPublish(page!);
      }
      console.log('   ✓ 已打开小红书发布页');

      console.log('\n🚀 步骤2: 切换到图文 Tab');
      await switchToImageTab(page!);
      console.log('   ✓ 已切换到图文 Tab');

      console.log('\n🚀 步骤3: 上传图片');
      await uploadImages(page!, imagePaths);
      console.log('   ✓ 图片上传中...');

      console.log('\n🚀 步骤4: 等待图片上传完成');
      await waitForUploadComplete(page!);
      console.log('   ✓ 图片上传完成');

      console.log('\n🚀 步骤5: 填入标题');
      await fillXhsTitle(page!, title);
      console.log(`   ✓ 标题已填入: ${title}`);

      console.log('\n🚀 步骤6: 填入正文');
      await fillXhsContent(page!, textContent);
      console.log('   ✓ 正文已填入');

      console.log('\n🚀 步骤7: 发布笔记');
      await publishNote(page!);
      console.log('   ✓ 笔记发布成功！');

      console.log('\n🎉 小红书自动化流程完成！');
    } catch (error) {
      console.error('\n❌ 发布失败:', (error as Error).message);
    } finally {
      clearTimeout(timeout);
      await browser?.close();
      process.exit(0);
    }
  });

program.parse(process.argv);
