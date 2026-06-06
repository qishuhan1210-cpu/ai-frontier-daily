import * as fs from 'fs';
import * as path from 'path';
import * as yaml from 'js-yaml';

const _configDir = path.resolve(__dirname, '..', '..', 'config');
const _raw = yaml.load(fs.readFileSync(path.join(_configDir, 'config.yaml'), 'utf8')) as any;

const { env, wechat, xhs } = _raw;

const _home = process.env.HOME || '';

// ============ 微信公众号配置 ============
export const CONFIG = {
  CHROME_PATH: env.chrome_path as string,
  USER_DATA_DIR: path.resolve((env.user_data_dir as string).replace('~', _home)),

  AUTH_FILE: path.resolve(_configDir, wechat.auth_file as string),
  BASE_DIR: path.resolve(_configDir, wechat.base_dir as string),
  HTML_FILENAME: wechat.html_filename as string,

  WECHAT_URL: wechat.wechat_url as string,
  LOGIN_CHECK_SELECTOR: wechat.login_check_selector as string,
  ARTICLE_BTN_SELECTOR: wechat.article_btn_selector as string,
  TITLE_SELECTOR: wechat.title_selector as string,
  EDITOR_SELECTOR: wechat.editor_selector as string,
  COVER_UPLOAD_SELECTOR: wechat.cover_upload_selector as string,
  SAVE_DRAFT_SELECTOR: wechat.save_draft_selector as string,

  COVER_IMAGE: path.resolve(_configDir, wechat.cover_image as string),

  ARTICLE_TITLE_TEMPLATE: wechat.article_title_template as string,
};

// ============ 小红书配置 ============
export const XHS_CONFIG = {
  XHS_AUTH_FILE: path.resolve(_configDir, xhs.auth_file as string),
  BASE_DIR: path.resolve(_configDir, xhs.base_dir as string),
  IMAGES_DIR_NAME: xhs.images_dir_name as string,

  XHS_URL: xhs.xhs_url as string,
  LOGIN_CHECK_SELECTOR: xhs.login_check_selector as string,
  IMAGE_TAB_SELECTOR: xhs.image_tab_selector as string,
  IMAGE_UPLOAD_SELECTOR: xhs.image_upload_selector as string,
  TITLE_SELECTOR: xhs.title_selector as string,
  EDITOR_SELECTOR: xhs.editor_selector as string,
  PUBLISH_CONFIRM_BTN_SELECTOR: xhs.publish_confirm_btn_selector as string,
  SCHEDULE_SWITCH_SELECTOR: xhs.schedule_switch_selector as string,
  SCHEDULE_DATETIME_SELECTOR: xhs.schedule_datetime_selector as string,
  SCHEDULE_TIME: xhs.schedule_time as string,

  ARTICLE_TITLE_TEMPLATE: xhs.article_title_template as string,
  TAGS: (xhs.tags as string[]) || [],
};
