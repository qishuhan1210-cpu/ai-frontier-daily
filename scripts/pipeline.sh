#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="/Users/han.qishu/.qclaw/skills/ai-frontier-daily"
DATE=$(date +%Y-%m-%d)

echo "======================================"
echo "AI前沿早报工作流  日期: $DATE"
echo "======================================"

# 0. 清理临时文件 + Output 历史日志（10天前及异常目录名）
echo ""
echo "[0/5] 清理临时文件..."
rm -f /tmp/afinfo-*.txt
OUTPUT_DIR="$SKILL_DIR/Output"
CUTOFF=$(date -v-10d +%Y-%m-%d 2>/dev/null || date -d "10 days ago" +%Y-%m-%d)
for dir in "$OUTPUT_DIR"/*/; do
  name=$(basename "$dir")
  if [[ ! "$name" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || [[ "$name" < "$CUTOFF" ]]; then
    rm -rf "$dir"
  fi
done
echo "  ✓ 清理完成"

# 1. 新闻采集
echo ""
echo "[1/5] 新闻采集..."
"$SKILL_DIR/scripts/base/run.sh" python project-space/news_frontier.py --date "$DATE"
echo "  ✓ 新闻采集完成"

# 2. 发布飞书文档
echo ""
echo "[2/5] 发布飞书文档..."
"$SKILL_DIR/scripts/base/run.sh" python scripts/pipeline/publish2lark.py --date "$DATE" > /tmp/afinfo-doc_url.txt
echo "  ✓ 飞书文档已发布: $(cat /tmp/afinfo-doc_url.txt)"

# 2.5 小红书卡片截图
echo ""
echo "[2.5/5] 小红书卡片截图..."
"$SKILL_DIR/scripts/base/run.sh" node "$SKILL_DIR/project-space2/node_modules/.bin/tsx" project-space2/src/services/screenshot-redbook-cdp.ts "$DATE"
echo "  ✓ 小红书截图完成"

# 3. 推送飞书群
echo ""
echo "[3/5] 推送飞书群..."
DOC_URL=$(cat /tmp/afinfo-doc_url.txt)
"$SKILL_DIR/scripts/base/run.sh" python scripts/pipeline/push2group.py --date "$DATE" --doc-url "$DOC_URL"
echo "  ✓ 飞书群推送完成"

# 4. 微信公众号草稿发布
echo ""
echo "[4/5] 微信公众号草稿发布..."
"$SKILL_DIR/scripts/base/run.sh" node "$SKILL_DIR/project-space2/node_modules/.bin/tsx" project-space2/src/main.ts publish "$DATE"
echo "  ✓ 微信草稿保存完成"
