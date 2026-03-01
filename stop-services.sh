#!/bin/bash
# 飞书Claude Bot 停止脚本

echo "停止飞书Claude Bot服务..."

# 方式1: 通过systemd停止
if systemctl --user is-active --quiet feishu-bot.service; then
    systemctl --user stop feishu-bot.service
    echo "✅ systemd服务已停止"
fi

# 方式2: 直接停止进程（备用）
pkill -f "feishu_websocket_client.py" 2>/dev/null
pkill -f "feishu_claude_local_bot.py" 2>/dev/null

# 清理消息队列
rm -f /tmp/feishu_messages.jsonl /tmp/feishu_processed.jsonl

echo "✅ 所有服务已停止"
