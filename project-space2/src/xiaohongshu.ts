#!/usr/bin/env node

import { Command } from 'commander';
import { XhsPublisher } from './services/xhs-publisher';

const MAX_TIMEOUT_MS = 10 * 60 * 1000;

const program = new Command();

program
  .name('xhs')
  .description('小红书自动化工具')
  .version('1.0.0');

program
  .command('save-auth')
  .description('引导用户授权登录小红书')
  .action(async () => {
    const publisher = new XhsPublisher();
    await publisher.saveAuth();
  });

program
  .command('publish [date]')
  .description('发布小红书图文笔记：上传图片 → 填标题 → 填正文 → 发布')
  .action(async (date?: string) => {
    const timeout = setTimeout(() => {
      console.error('\n⏱️ 运行超时10分钟，强制退出');
      process.exit(1);
    }, MAX_TIMEOUT_MS);
    timeout.unref();

    try {
      const publisher = new XhsPublisher(date);
      await publisher.publish();
    } catch (error) {
      console.error('\n❌ 发布失败:', (error as Error).message);
    } finally {
      clearTimeout(timeout);
      process.exit(0);
    }
  });

program.parse(process.argv);
