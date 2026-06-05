#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish2lark.py — 将 AI 前沿早报发布到飞书知识库"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# 路径设置
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_SECRETS_FILE = _PROJECT_ROOT / 'config' / 'secrets.json'


# 导入 WorkModule 基类
sys.path.insert(0, str(_PROJECT_ROOT / 'project-space'))
from utils.work_module import WorkModule
from utils.base_config import FN_BRIEFING_FEISHU
from utils.lark_commander import LarkCmd
#todo: 之后废弃掉 LarkCmd直接sdk 调用 兼容过程太麻烦了


class LarkWikiPublisher(WorkModule):
    """飞书知识库发布器（继承自 WorkModule，复用日志和通用方法）"""
    
    def __init__(self, date: str):
        super().__init__('publish2lark', date)
        self.date = date
        self.output_dir = _PROJECT_ROOT / 'output' / date
        self.briefing_file = self.output_dir / FN_BRIEFING_FEISHU
        
        # 加载配置
        with open(_SECRETS_FILE, 'r', encoding='utf-8') as f:
            self.space_id = json.load(f)['feishu']['space_id']
        
        # 确保输出目录存在
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _find_or_create_node(self, title: str) -> Optional[str]:
        """查找或创建 wiki 节点"""
        query = f'.data.nodes[] | select(.title == "{title}") | .node_token'
        token = LarkCmd.WIKI_NODE_LIST.args(space_id=self.space_id, query=query).run()
        if token:
            return token
        return LarkCmd.WIKI_NODE_CREATE.args(space_id=self.space_id, title=title).run()
    
    def _find_or_create_month_folder(self) -> Optional[str]:
        """查找或创建月份文件夹"""
        month = self.date[:7]
        self.logger.info(f"=== Step 1/5: 查找或创建月份文件夹 '{month}' ===")
        token = self._find_or_create_node(month)
        if token:
            self.logger.info(f"月份文件夹 Token: {token}")
        return token
    
    def _check_output(self) -> bool:
        """检查早报文件"""
        self.logger.info("=== Step 2/5: 检查输出文件 ===")
        if self.briefing_file.exists():
            size = self.briefing_file.stat().st_size
            lines = sum(1 for _ in open(self.briefing_file))
            self.logger.info(f"找到早报文件: {self.briefing_file} (大小: {size} bytes, 行数: {lines})")
            return True
        self.logger.error(f"早报文件不存在: {self.briefing_file}")
        return False
    
    def _clean_duplicates(self, parent_token: str) -> None:
        """清理重复文档"""
        self.logger.info("=== Step 3/5: 检查并清理已存在的当日早报 ===")
        title_pattern = f"AI 前沿早报（{self.date}）"
        query = f'[.data.nodes[] | select(.title | contains("{title_pattern}")) | .node_token]'
        output = LarkCmd.WIKI_NODE_LIST_BY_PARENT.args(
            space_id=self.space_id,
            parent_token=parent_token,
            query=query
        ).run()
        
        if not output:
            self.logger.info("未找到已存在的早报文档，跳过清理")
            return
        
        try:
            nodes = json.loads(output)
        except json.JSONDecodeError:
            self.logger.info("未找到已存在的早报文档，跳过清理")
            return
        
        if not isinstance(nodes, list) or len(nodes) == 0:
            self.logger.info("未找到已存在的早报文档，跳过清理")
            return
        
        self.logger.warning(f"找到 {len(nodes)} 个重复文档，移入回收站...")
        trash_token = self._find_or_create_node("回收站")
        if not trash_token:
            self.logger.error("无法创建或找到回收站文件夹")
            return
        
        self.logger.info(f"回收站文件夹 Token: {trash_token}")
        moved = 0
        for token in nodes:
            if token and token != 'null':
                self.logger.info(f"移动文档 {token} 至回收站...")
                if LarkCmd.WIKI_NODE_MOVE.args(node_token=token, target_parent_token=trash_token, space_id=self.space_id).run():
                    moved += 1
        self.logger.info(f"已将 {moved} 个旧文档移入回收站")
    
    def _publish(self, parent_token: str) -> Optional[str]:
        """发布早报文档"""
        self.logger.info("=== Step 4/5: 创建并发布早报文档 ===")
        
        title = f"AI 前沿早报（{self.date}）"
        node_token = LarkCmd.WIKI_NODE_CREATE_WITH_PARENT.args(
            space_id=self.space_id,
            title=title,
            parent_token=parent_token
        ).run()
        
        if not node_token:
            self.logger.error("节点创建失败")
            return None
        self.logger.info(f"节点创建成功，Doc Token: {node_token}")
        
        self.logger.info("开始写入文档内容...")
        with open(self.briefing_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not LarkCmd.DOC_UPDATE.args(doc_token=node_token, title=title).input(content).run():
            self.logger.error("文档内容写入失败")
            return None
        
        self.logger.info("文档内容写入成功")
        url = f"https://my.feishu.cn/wiki/{node_token}"
        print(url)
        return url
    
    def run(self) -> int:
        """执行完整发布流程"""
        sep = "=" * 63
        self.logger.info(sep)
        self.logger.info("=== 开始发布 AI 前沿早报到飞书知识库 ===")
        self.logger.info(f"发布日期: {self.date}")
        self.logger.info(sep)
        
        parent_token = self._find_or_create_month_folder()
        if not parent_token:
            self.logger.error("无法创建或找到月份文件夹")
            return 1
        self.logger.info(f"目标目录: {self.date[:7]} (Token: {parent_token})")
        
        if not self._check_output():
            return 1
        
        self._clean_duplicates(parent_token)
        url = self._publish(parent_token)
        
        self.logger.info("=== Step 5/5: 发布完成 ===")
        self.logger.info(sep)
        if url:
            self.logger.info(f"AI 前沿早报（{self.date}）已发布到飞书知识库")
            self.logger.info(sep)
            return 0
        self.logger.error("发布失败")
        self.logger.info(sep)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description='将 AI 前沿早报发布到飞书知识库')
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'), help='日期 (YYYY-MM-DD)')
    return LarkWikiPublisher(parser.parse_args().date).run()


if __name__ == '__main__':
    sys.exit(main())
