#!/usr/bin/env node
/**
 * screenshot-redbook-cdp.ts — 小红书卡片批量截图（Chrome CDP 版）
 *
 * 用法: npx tsx screenshot-redbook-cdp.ts [date]
 *   date: 日期，格式 YYYY-MM-DD，默认今天
 *
 * 输入: output/{date}/redbook/*.html
 * 输出: output/{date}/redbook-png/*.png
 *
 * 架构: CDPClient → HeadlessBrowser → RedbookScreenshot
 */

import { spawn, ChildProcess } from 'child_process';
import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as http from 'http';
import * as net from 'net';

// ============ Config — 统一配置管理 ============
class Config {
  static CHROME_BIN: string = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

  // 截图参数
  static DEVICE_SCALE: number = 2;
  static PADDING: number = 5;

  // 视口参数
  static VIEWPORT_WIDTH: number = 1200;
  static VIEWPORT_HEIGHT: number = 2000;
  static WINDOW_SIZE: string = `${Config.VIEWPORT_WIDTH},${Config.VIEWPORT_HEIGHT}`;
  static HEADLESS: boolean = true;

  // 时序参数
  static CDP_TIMEOUT: number = 15000;
  static CHROME_READY_RETRIES: number = 60;
  static CHROME_READY_INTERVAL: number = 500;
  static PAGE_NAVIGATE_WAIT: number = 500;
  static SCREENSHOT_WAIT: number = 200;

  // 卡片选择器（按优先级）
  static CARD_SELECTORS: string[] = ['section.quick-view-card', 'section.news-card'];

  // 目录结构（从 project-space2/src/services/ 向上三级到项目根，再进 output/）
  static BASE_DIR: string = path.resolve(__dirname, '..', '..', '..', 'output');
  static REDBOOK_SUBDIR: string = 'redbook';
  static OUTPUT_SUBDIR: string = 'redbook-png';
}

// ============ Logger ============
class Logger {
  static NAME: string = 'screenshot-redbook-cdp';
  private _logFile: string;

  constructor(date: string) {
    const logDir = path.resolve(Config.BASE_DIR, date);
    fs.mkdirSync(logDir, { recursive: true });
    this._logFile = path.join(logDir, 'run.log');
  }

  private _write(level: string, msg: string): void {
    const ts = new Date().toISOString().replace('T', ' ').slice(0, 19);
    const line = `${ts} - ${Logger.NAME} - ${level.padEnd(8)} - ${msg}\n`;
    fs.appendFileSync(this._logFile, line, 'utf-8');
  }

  info(msg: string): void    { console.log(msg);   this._write('INFO', msg); }
  warning(msg: string): void { console.warn(msg);  this._write('WARNING', msg); }
}

// ============ CDPClient — WebSocket 通信层 ============
interface PendingCallback {
  resolve: (value: any) => void;
  reject: (reason: Error) => void;
}

class CDPClient {
  private _wsUrl: string;
  private _msgId: number;
  private _pending: Map<number, PendingCallback>;
  private _buf: Buffer;
  private _sock: net.Socket | null;

  constructor(wsUrl: string) {
    this._wsUrl = wsUrl;
    this._msgId = 1;
    this._pending = new Map();
    this._buf = Buffer.alloc(0);
    this._sock = null;
  }

  connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const url = new URL(this._wsUrl);
      this._sock = net.createConnection({ host: url.hostname, port: parseInt(url.port) }, () => {
        const key = Buffer.from(Math.random().toString()).toString('base64');
        this._sock!.write([
          `GET ${url.pathname} HTTP/1.1`,
          `Host: ${url.host}`,
          'Upgrade: websocket',
          'Connection: Upgrade',
          `Sec-WebSocket-Key: ${key}`,
          'Sec-WebSocket-Version: 13',
          '', '',
        ].join('\r\n'));
      });
      this._sock.once('data', (chunk: Buffer) => {
        if (chunk.toString().includes('101')) {
          this._sock!.on('data', (c: Buffer) => this._onFrame(c));
          resolve();
        } else {
          reject(new Error('WebSocket 握手失败'));
        }
      });
      this._sock.on('error', reject);
    });
  }

  private _onFrame(chunk: Buffer): void {
    this._buf = Buffer.concat([this._buf, chunk]);
    while (this._buf.length >= 2) {
      const b1 = this._buf[1];
      const masked = (b1 & 0x80) !== 0;
      let payloadLen = b1 & 0x7f;
      let offset = 2;
      if (payloadLen === 126) {
        if (this._buf.length < 4) break;
        payloadLen = this._buf.readUInt16BE(2); offset = 4;
      } else if (payloadLen === 127) {
        if (this._buf.length < 10) break;
        payloadLen = Number(this._buf.readBigUInt64BE(2)); offset = 10;
      }
      const total = offset + (masked ? 4 : 0) + payloadLen;
      if (this._buf.length < total) break;
      let payload = this._buf.slice(offset + (masked ? 4 : 0), total);
      if (masked) {
        const mask = this._buf.slice(offset, offset + 4);
        payload = Buffer.from(payload.map((b: number, i: number) => b ^ mask[i % 4]));
      }
      this._buf = this._buf.slice(total);
      try {
        const msg = JSON.parse(payload.toString());
        const cb = this._pending.get(msg.id);
        if (cb) {
          this._pending.delete(msg.id);
          msg.error ? cb.reject(new Error(msg.error.message)) : cb.resolve(msg.result);
        }
      } catch {}
    }
  }

  private _frame(data: string): Buffer {
    const payload = Buffer.from(data);
    const len = payload.length;
    let header: Buffer;
    if (len < 126) {
      header = Buffer.from([0x81, 0x80 | len]);
    } else if (len < 65536) {
      header = Buffer.alloc(4);
      header[0] = 0x81; header[1] = 0x80 | 126;
      header.writeUInt16BE(len, 2);
    } else {
      header = Buffer.alloc(10);
      header[0] = 0x81; header[1] = 0x80 | 127;
      header.writeBigUInt64BE(BigInt(len), 2);
    }
    const mask = Buffer.alloc(4);
    const masked = Buffer.from(payload.map((b: number, i: number) => b ^ mask[i % 4]));
    return Buffer.concat([header, mask, masked]);
  }

  send(method: string, params: object = {}): Promise<any> {
    return new Promise((resolve, reject) => {
      const id = this._msgId++;
      this._pending.set(id, { resolve, reject });
      this._sock!.write(this._frame(JSON.stringify({ id, method, params })));
      setTimeout(() => {
        if (this._pending.has(id)) {
          this._pending.delete(id);
          reject(new Error(`CDP timeout: ${method}`));
        }
      }, Config.CDP_TIMEOUT);
    });
  }

  close(): void { try { this._sock?.destroy(); } catch {} }
}

// ============ HeadlessBrowser — Chrome 进程管理 + CDP 操作 ============
interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

class HeadlessBrowser {
  private _proc: ChildProcess | null;
  private _cdp: CDPClient | null;
  private _port: number | null;

  constructor() {
    this._proc = null;
    this._cdp = null;
    this._port = null;
  }

  private static _findFreePort(): Promise<number> {
    return new Promise((resolve, reject) => {
      const srv = net.createServer();
      srv.listen(0, '127.0.0.1', () => {
        const p = (srv.address() as net.AddressInfo).port;
        srv.close(() => resolve(p));
      });
      srv.on('error', reject);
    });
  }

  private static _httpGet(url: string): Promise<string> {
    return new Promise((resolve, reject) => {
      http.get(url, res => {
        let d = '';
        res.on('data', (c: string) => d += c);
        res.on('end', () => resolve(d));
      }).on('error', reject);
    });
  }

  private static _sleep(ms: number): Promise<void> {
    return new Promise(r => setTimeout(r, ms));
  }

  async launch(): Promise<void> {
    this._port = await HeadlessBrowser._findFreePort();
    const userDataDir = path.join(os.tmpdir(), `chrome-cdp-${Date.now()}`);
    fs.mkdirSync(userDataDir, { recursive: true });

    this._proc = spawn(Config.CHROME_BIN, [
      `--user-data-dir=${userDataDir}`,
      '--no-first-run', '--no-default-browser-check',
      '--disable-gpu', '--hide-scrollbars',
      '--no-sandbox', '--disable-extensions',
      `--remote-debugging-port=${this._port}`,
      `--window-size=${Config.WINDOW_SIZE}`,
      Config.HEADLESS ? '--headless=new' : '',
    ].filter(Boolean), { stdio: ['pipe', 'pipe', 'pipe'] });

    await this._waitReady();
    const tabs: any[] = JSON.parse(
      await HeadlessBrowser._httpGet(`http://127.0.0.1:${this._port}/json/list`)
    );
    const tab = tabs.find((t: any) => t.type === 'page');
    if (!tab) throw new Error('未找到 Chrome page tab');

    this._cdp = new CDPClient(tab.webSocketDebuggerUrl);
    await this._cdp.connect();
    await this._cdp.send('Page.enable');
  }

  private async _waitReady(): Promise<void> {
    for (let i = 0; i < Config.CHROME_READY_RETRIES; i++) {
      try {
        await HeadlessBrowser._httpGet(`http://127.0.0.1:${this._port}/json/version`);
        return;
      } catch {
        await HeadlessBrowser._sleep(Config.CHROME_READY_INTERVAL);
      }
    }
    throw new Error('Chrome 启动超时');
  }

  async open(fileUrl: string): Promise<void> {
    await this._cdp!.send('Page.navigate', { url: fileUrl });
    await HeadlessBrowser._sleep(Config.PAGE_NAVIGATE_WAIT);
  }

  async queryRect(selector: string): Promise<Rect | null> {
    const res = await this._cdp!.send('Runtime.evaluate', {
      expression: `(function(){
        const el = document.querySelector('${selector}');
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.x, y: r.y, width: r.width, height: r.height };
      })()`,
      returnByValue: true,
    });
    return res?.result?.value ?? null;
  }

  async screenshot(rect: Rect, outputPath: string): Promise<number> {
    const clipX = Math.max(0, Math.floor(rect.x) - Config.PADDING);
    const clipY = Math.max(0, Math.ceil(rect.y) - Config.PADDING);
    const clipW = Math.max(0, Math.ceil(rect.width) + 2 * Config.PADDING);
    const clipH = Math.max(0, Math.ceil(rect.height) + 2 * Config.PADDING);

    await this._cdp!.send('Emulation.setDeviceMetricsOverride', {
      width: Config.VIEWPORT_WIDTH,
      height: Config.VIEWPORT_HEIGHT,
      deviceScaleFactor: Config.DEVICE_SCALE,
      mobile: false,
    });
    await HeadlessBrowser._sleep(Config.SCREENSHOT_WAIT);

    const res = await this._cdp!.send('Page.captureScreenshot', {
      format: 'png',
      clip: { x: clipX, y: clipY, width: clipW, height: clipH, scale: 1 },
    });

    fs.writeFileSync(outputPath, Buffer.from(res.data, 'base64'));
    return fs.statSync(outputPath).size;
  }

  close(): void {
    try { this._cdp?.close(); } catch {}
    try { this._proc?.kill('SIGKILL'); } catch {}
  }
}

// ============ RedbookScreenshot — 业务流程层 ============
class RedbookScreenshot {
  private date: string;
  private redbookDir: string;
  private outputDir: string;
  private logger: Logger;
  private htmlFiles: string[] = [];

  constructor(date: string) {
    this.date = date;
    this.redbookDir = path.join(Config.BASE_DIR, date, Config.REDBOOK_SUBDIR);
    this.outputDir = path.join(Config.BASE_DIR, date, Config.OUTPUT_SUBDIR);
    this.logger = new Logger(date);
  }

  validate(): this {
    if (!fs.existsSync(this.redbookDir)) throw new Error(`redbook 目录不存在: ${this.redbookDir}`);
    if (!fs.existsSync(Config.CHROME_BIN)) throw new Error(`未找到 Chrome: ${Config.CHROME_BIN}`);

    this.htmlFiles = fs.readdirSync(this.redbookDir)
      .filter((f: string) => f.endsWith('.html')).sort()
      .map((f: string) => path.join(this.redbookDir, f));

    if (this.htmlFiles.length === 0) throw new Error('redbook 目录中没有 HTML 文件');
    fs.mkdirSync(this.outputDir, { recursive: true });
    return this;
  }

  logSummary(): void {
    this.logger.info(`📁 日期: ${this.date}`);
    this.logger.info(`📁 输入: ${this.redbookDir}`);
    this.logger.info(`📁 输出: ${this.outputDir}`);
    this.logger.info(` 缩放: ${Config.DEVICE_SCALE}x`);
    this.logger.info(`📄 找到 ${this.htmlFiles.length} 个文件`);
  }

  async processOne(browser: HeadlessBrowser, htmlFile: string, index: number, total: number): Promise<boolean> {
    const basename = path.basename(htmlFile, '.html');
    this.logger.info(` [${index + 1}/${total}] 处理: ${basename}.html`);

    await browser.open(`file://${htmlFile}`);
    this.logger.info('  ✓ 页面已加载');

    let rect: Rect | null = null;
    let matched: string | null = null;
    for (const sel of Config.CARD_SELECTORS) {
      rect = await browser.queryRect(sel);
      if (rect) { matched = sel; break; }
    }
    if (!rect) {
      this.logger.warning('  ⚠️  未找到已知卡片类型，跳过');
      return false;
    }
    this.logger.info(`  ✓ 卡片: ${matched}  尺寸: ${Math.ceil(rect.width)}x${Math.ceil(rect.height)}`);

    const outputFile = path.join(this.outputDir, `${basename}.png`);
    const size = await browser.screenshot(rect, outputFile);
    this.logger.info(`  ✅ 已保存: ${basename}.png (${size} bytes)`);
    return true;
  }

  async run(): Promise<{ total: number; success: number }> {
    this.validate();
    this.logSummary();

    const browser = new HeadlessBrowser();
    await browser.launch();
    let success = 0;

    try {
      for (let i = 0; i < this.htmlFiles.length; i++) {
        if (await this.processOne(browser, this.htmlFiles[i], i, this.htmlFiles.length)) {
          success++;
        }
      }
    } finally {
      browser.close();
    }

    this.logger.info(' 批量截图完成！');
    this.logger.info(`📁 输出目录: ${this.outputDir}`);
    this.logger.info(`📊 共处理 ${this.htmlFiles.length} 个文件，成功 ${success} 个`);
    return { total: this.htmlFiles.length, success };
  }
}

// ============ 入口 ============
const date = process.argv[2] || new Date().toISOString().slice(0, 10);
new RedbookScreenshot(date).run().catch((err: Error) => {
  console.error('❌ 错误:', err.message);
  process.exit(1);
});
