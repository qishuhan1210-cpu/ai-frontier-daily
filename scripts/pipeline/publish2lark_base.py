#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish2lark_base.py — 将 AI 前沿早报数据同步到飞书多维表格"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# 路径设置
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_SECRETS_FILE = _PROJECT_ROOT / 'config' / 'secrets.json'

sys.path.insert(0, str(_PROJECT_ROOT / 'project-space'))
from utils.logger import get_logger
from utils.lark_commander import LarkCmd


class LarkBasePublisher:
    """飞书多维表格发布器"""
    
    # 字段类型映射
    FIELD_TYPE_MAP = {
        str: 'text',
        int: 'number',
        float: 'number',
        list: 'text',
    }
    
    def __init__(self, date: str):
        self.date = date
        self.output_dir = _PROJECT_ROOT / 'output' / date
        self.summary_file = self.output_dir / 'summary.json'

        with open(_SECRETS_FILE, 'r', encoding='utf-8') as f:
            secrets = json.load(f)
            self.base_token = secrets['feishu'].get('base_token', '')
            self.table_id = secrets['feishu'].get('table_id', '')
            self.space_id = secrets['feishu'].get('space_id', '')

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger('publish2lark_base', date)

        self.field_name_to_id = {}
        self.field_name_to_type = {}

    def _load_summary(self) -> Optional[List[Dict]]:
        """加载早报数据，并为每条记录添加date字段"""
        self.logger.info("=== 加载早报数据 ===")
        if not self.summary_file.exists():
            self.logger.error(f"早报数据文件不存在: {self.summary_file}")
            return None
        
        with open(self.summary_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        items = data.get('clusters', [])
        
        # 为每条记录添加date字段和daily_report_time字段（使用同步日期）
        for item in items:
            item['date'] = self.date
            item['daily_report_time'] = self.date  # 日报时间字段，用于record-search查询
        
        self.logger.info(f"成功加载 {len(items)} 条早报数据")
        return items

    def _create_base_if_not_exists(self) -> Optional[str]:
        """如果没有配置 base_token，则查找或创建名为'AI前沿早报数据库'的多维表格"""
        if self.base_token:
            self.logger.info(f"使用已配置的 Base: {self.base_token}")
            return self.base_token
        
        self.logger.info("=== 查找已存在的'AI前沿早报数据库' ===")
        if not self.space_id:
            self.logger.error("未配置 space_id，无法在知识库中搜索")
            return None
        
        result = LarkCmd.WIKI_NODE_SEARCH_BITABLE.args(space_id=self.space_id, keyword='AI前沿早报数据库').run(logger=self.logger)
        
        if result:
            try:
                items = json.loads(result)
                if isinstance(items, list) and len(items) > 0:
                    self.base_token = items[0].get('obj_token', '')
                elif isinstance(items, dict) and items.get('obj_token'):
                    self.base_token = items.get('obj_token', '')
                if self.base_token:
                    self.logger.info(f"找到已存在的多维表格: {self.base_token}")
                    return self.base_token
            except json.JSONDecodeError as e:
                self.logger.warning(f"解析搜索结果失败: {e}")
        
        self.logger.info("=== 创建新的多维表格 ===")
        result = LarkCmd.BASE_CREATE.args(name='AI前沿早报数据库', timezone='Asia/Shanghai').run(logger=self.logger)
        if result:
            self.base_token = result
            self.logger.info(f"成功创建多维表格: {self.base_token}")
            return self.base_token
        self.logger.error("创建多维表格失败")
        return None
    
    def _create_table_if_not_exists(self) -> Optional[str]:
        """查找或创建名为'早报记录'的数据表"""
        if self.table_id:
            self.logger.info(f"使用已配置的表格: {self.table_id}")
            return self.table_id
        
        self.logger.info("=== 查找已存在的'早报记录'表 ===")
        result = LarkCmd.BASE_TABLE_LIST.args(base_token=self.base_token).run(logger=self.logger)
        
        if result:
            try:
                tables = json.loads(result)
                for table in tables:
                    if table.get('name') == '早报记录':
                        self.table_id = table.get('id')
                        self.logger.info(f"找到已存在的表格'早报记录': {self.table_id}")
                        return self.table_id
            except Exception as e:
                self.logger.warning(f"解析表格列表失败: {e}")
        
        self.logger.info("=== 创建新的数据表'早报记录' ===")
        table_id = LarkCmd.BASE_TABLE_CREATE.args(
            base_token=self.base_token,
            table_json=json.dumps({"name": "早报记录"}, ensure_ascii=False)
        ).run(logger=self.logger)
        
        if not table_id:
            self.logger.error("无法创建数据表")
            return None
        
        self.table_id = table_id
        self.logger.info(f"成功创建数据表'早报记录': {self.table_id}")
        return self.table_id

    def _get_field_type(self, value: Any) -> str:
        """根据 Python 数据类型返回飞书字段类型"""
        if isinstance(value, bool):
            return 'checkbox'
        elif isinstance(value, (int, float)):
            return 'number'
        elif isinstance(value, list):
            # 数组类型使用文本字段，用逗号分隔存储
            return 'text'
        elif isinstance(value, str):
            if value.startswith('http://') or value.startswith('https://'):
                return 'url'
            return 'text'
        return 'text'

    def _sync_fields(self, items: List[Dict]):
        """同步字段：根据summary.json动态创建不存在的字段"""
        self.logger.info("=== 同步字段 ===")
        
        result = LarkCmd.BASE_FIELD_LIST.args(
            base_token=self.base_token,
            table_id=self.table_id
        ).run(logger=self.logger)
        
        existing_fields = {}
        if result:
            try:
                fields = json.loads(result)
                for f in fields:
                    existing_fields[f['name']] = {'field_id': f['field_id'], 'type': str(f['type'])}
            except Exception as e:
                self.logger.warning(f"解析已有字段失败: {e}")
        
        self.field_name_to_id = {name: info['field_id'] for name, info in existing_fields.items()}
        self.field_name_to_type = {name: info['type'] for name, info in existing_fields.items()}
        
        # 从所有记录中收集所有字段
        all_field_names = set()
        for item in items:
            all_field_names.update(item.keys())
        
        # 过滤掉私有字段（以下划线开头）
        all_field_names = {name for name in all_field_names if not name.startswith('_')}
        
        self.logger.info(f"发现 {len(all_field_names)} 个字段需要处理")
        
        for field_name in sorted(all_field_names):
            if field_name in existing_fields:
                # 检查已存在的date字段类型是否正确
                if field_name == 'date' and existing_fields[field_name]['type'] != 'date':
                    self.logger.warning(f"date字段类型不正确，当前为 {existing_fields[field_name]['type']}，需要手动修改为日期类型")
                self.logger.info(f"字段 '{field_name}' 已存在，跳过")
                continue
            
            # date字段强制使用日期类型，daily_report_time字段强制使用文本类型（方便搜索）
            if field_name == 'date':
                field_type = 'date'
            elif field_name == 'daily_report_time':
                field_type = 'text'
            else:
                sample_values = [item.get(field_name) for item in items[:5] if item.get(field_name) is not None]
                if not sample_values:
                    field_type = 'text'
                else:
                    field_type = self._get_field_type(sample_values[0])
            
            field_json = {"name": field_name, "type": field_type}
            
            result = LarkCmd.BASE_FIELD_CREATE.args(
                base_token=self.base_token,
                table_id=self.table_id,
                field_json=json.dumps(field_json, ensure_ascii=False)
            ).run(logger=self.logger)
            if result:
                self.field_name_to_id[field_name] = result
                self.field_name_to_type[field_name] = field_type
                self.logger.info(f"成功创建字段 '{field_name}' (type={field_type}): {result}")
            else:
                self.logger.warning(f"创建字段 '{field_name}' 失败")

    def _convert_value(self, value: Any, field_type: str) -> Any:
        """将 Python 值转换为飞书 API 格式"""
        if value is None:
            return None
        # 数组类型转换为逗号分隔的字符串
        if isinstance(value, list):
            return ','.join(str(v) for v in value)
        return value



    def _delete_today_records(self) -> int:
        """删除当天日期的所有记录（使用搜索过滤，支持分页）"""
        date_field_id = "daily_report_time"
        if not date_field_id:
            self.logger.warning("date字段不存在，跳过删除操作")
            return 0
        
        self.logger.info(f"=== 删除 {self.date} 的所有记录 ===")
        
        deleted_count = 0
        batch_size = 200
        offset = 0
        
        # 收集所有当天的record_id（支持分页）
        today_record_ids = []
        
        while True:
            # 使用record-search按日期搜索当天的记录
            search_json = json.dumps({
                "keyword": self.date,
                "search_fields": [date_field_id],
                "select_fields": [date_field_id],
                "limit": batch_size,
                "offset": offset
            })
            
            result = LarkCmd.BASE_RECORD_SEARCH.args(
                base_token=self.base_token,
                table_id=self.table_id,
                search_json=search_json
            ).run(logger=self.logger)
            if not result:
                break
            
            try:
                search_result = json.loads(result)
                data = search_result.get('data', {})
                items = data.get('data', [])
                record_ids = data.get('record_id_list', [])
                field_ids = data.get('field_id_list', [])
                
                if not items or not record_ids:
                    break
                
                # 找到date字段在field_ids中的索引
                date_field_index = -1
                for i, fid in enumerate(field_ids):
                    if fid == date_field_id:
                        date_field_index = i
                        break
                
                if date_field_index == -1:
                    self.logger.warning("无法找到date字段索引")
                    break
                
                # 收集当天的record_id（精确匹配日期）
                for i, item in enumerate(items):
                    record_date = item[date_field_index] if len(item) > date_field_index else None
                    if record_date == self.date and i < len(record_ids):
                        today_record_ids.append(record_ids[i])
                
                # 如果返回的记录数少于batch_size，说明已经到最后一页
                if len(items) < batch_size:
                    break
                
                offset += batch_size
                
            except Exception as e:
                self.logger.warning(f"搜索记录失败: {e}")
                break
        
        # 批量删除
        if today_record_ids:
            self.logger.info(f"找到 {len(today_record_ids)} 条 {self.date} 的记录需要删除")
            
            # 分批删除，每次最多删除200条
            for i in range(0, len(today_record_ids), batch_size):
                batch_record_ids = today_record_ids[i:i+batch_size]
                delete_json = json.dumps({"record_id_list": batch_record_ids})
                delete_result = LarkCmd.BASE_RECORD_DELETE.args(
                    base_token=self.base_token,
                    table_id=self.table_id,
                    delete_json=delete_json
                ).run()
                if delete_result:
                    deleted_ids = json.loads(delete_result)
                    deleted_count += len(deleted_ids)
                    self.logger.info(f"已删除 {len(deleted_ids)} 条记录")
        
        self.logger.info(f"共删除 {deleted_count} 条 {self.date} 的记录")
        return deleted_count

    def _upload_records(self, items: List[Dict]):
        """批量上传记录（先删除当天数据再新增）"""
        self.logger.info(f"=== 处理 {len(items)} 条记录 ===")
        
        # 获取所有可写字段的ID列表
        field_ids = [fid for fid in self.field_name_to_id.values() if fid]

        field_names = [fid for fid in self.field_name_to_id.keys() if fid]

        
        if not field_ids:
            self.logger.error("没有可写的字段")
            return
        
        # 先删除当天的所有记录
        self._delete_today_records()
        
        # 构建数据行：[[value1, value2, ...], [value1, value2, ...], ...]
        rows = []
        for item in items:
            row = []
            for field_id in field_ids:
                # 根据field_id找到对应的field_name
                field_name = None
                for name, fid in self.field_name_to_id.items():
                    if fid == field_id:
                        field_name = name
                        break
                
                if field_name and field_name.startswith('_'):
                    row.append(None)
                    continue
                
                value = item.get(field_name) if field_name else None
                if value is not None:
                    field_type = self.field_name_to_type.get(field_name, 'text') if field_name else 'text'
                    row.append(self._convert_value(value, field_type))
                else:
                    row.append(None)
            
            rows.append(row)
        
        if not rows:
            self.logger.info("没有记录需要上传")
            return

        batch_size = 50
        uploaded = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            data = json.dumps({
                "fields": field_names,
                "field_types": self.field_name_to_type,
                "rows": batch
            }, ensure_ascii=False)

            result = LarkCmd.BASE_RECORD_BATCH_CREATE.args(
                base_token=self.base_token,
                table_id=self.table_id,
                data_json=data
            ).run(logger=self.logger)
            if result:
                try:
                    record_ids = json.loads(result)
                    uploaded += len(record_ids)
                    self.logger.info(f"成功上传 {len(record_ids)} 条记录")
                except Exception as e:
                    self.logger.error(f"解析上传结果失败: {e}")
            else:
                self.logger.error(f"上传第 {i//batch_size + 1} 批记录失败")

        self.logger.info(f"本次共上传 {uploaded} 条记录")
    
    def run(self) -> int:
        """执行完整同步流程"""
        sep = "=" * 63
        self.logger.info(sep)
        self.logger.info("=== 开始同步 AI 前沿早报到飞书多维表格 ===")
        self.logger.info(f"同步日期: {self.date}")
        self.logger.info(sep)
        
        items = self._load_summary()
        if not items:
            return 1
        
        if not self._create_base_if_not_exists():
            return 1
        
        if not self._create_table_if_not_exists():
            return 1
        
        self._sync_fields(items)
        
        self._upload_records(items)
        
        self.logger.info("=== 同步完成 ===")
        self.logger.info(sep)
        self.logger.info(f"多维表格链接: https://my.feishu.cn/base/{self.base_token}")
        print(f"https://my.feishu.cn/base/{self.base_token}")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='将 AI 前沿早报数据同步到飞书多维表格')
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'), help='日期 (YYYY-MM-DD)')
    return LarkBasePublisher(parser.parse_args().date).run()


if __name__ == '__main__':
    sys.exit(main())