#!/usr/bin/env node

import { Command } from 'commander';
import { WechatPublisher } from './services/wechat-publisher';

const MAX_TIMEOUT_MS = 10 * 60 * 1000;

const program = new Command();

program
  .name('wechat-mp')
  .description('微信公众号自动化工具')
  .version('1.0.0');

program
  .command('save-auth')
  .description('引导用户授权登录')
  .action(async () => {
    const publisher = new WechatPublisher();
    await publisher.saveAuth();
  });

program
  .command('publish [date]')
  .description('发布新闻草稿: 浏览器打开新闻HTML&COPY -> 打开公众号新闻编辑页 -> 填充标题&正文 -> 保存草稿&退出浏览器')
  .action(async (date?: string) => {

    const timeout = setTimeout(() => {
      console.error('\n⏱️ 运行超时10分钟，强制退出');
      process.exit(1);
    }, MAX_TIMEOUT_MS);
    timeout.unref();

    try {
      await new WechatPublisher(date).publish();
    } catch (error) {
      console.error('\n❌ 发布失败:', (error as Error).message);
    } finally {
      clearTimeout(timeout);
      process.exit(0);
    }
    
  });

program.parse(process.argv);