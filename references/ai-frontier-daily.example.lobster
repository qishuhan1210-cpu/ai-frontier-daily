name: ai-frontier-daily
description: AI前沿早报工作流 (路径安全版)

args:
  date:
    default: $(date +%Y-%m-%d)

env:
  # 🔑 核心：定义项目根目录，彻底消灭相对路径带来的不确定性
  SKILL_DIR: $YOUR_PATH/ai-frontier-daily

steps:
  # 0. 清理临时文件 (保障每次运行环境干净)
  - id: cleanup
    command: bash -c 'rm -f /tmp/afinfo-*.txt'

  # 1. 新闻采集
  - id: news_frontier
    command: $SKILL_DIR/scripts/base/run.sh python project-space/news_frontier.py --date $(date +%Y-%m-%d)

  # 2. 发布飞书文档 (重定向到 /tmp 目录)
  - id: publish2lark
    command: bash -c '$SKILL_DIR/scripts/base/run.sh python scripts/pipeline/publish2lark.py --date $(date +%Y-%m-%d) > /tmp/afinfo-doc_url.txt'

  # 3. 推送飞书群 (从 /tmp 读取文件)
  - id: push2group
    command: bash -c 'DOC_URL=$(cat /tmp/afinfo-doc_url.txt) && $SKILL_DIR/scripts/base/run.sh python scripts/pipeline/push2group.py --date $(date +%Y-%m-%d) --doc-url "$DOC_URL"'

  # 4. 更新多维表格
  - id: publish2lark_base
    command: bash -c '$SKILL_DIR/scripts/base/run.sh python scripts/pipeline/publish2lark_base.py --date $(date +%Y-%m-%d) > /tmp/afinfo-base_url.txt'

  # 5. 最终报告
  - id: final_report
    command: bash -c 'echo "✅ 完成！\n📄 文档：$(cat /tmp/afinfo-doc_url.txt)\n📊 表格：$(cat /tmp/afinfo-base_url.txt)"'