#!/bin/bash
# 飞书Claude Bot 状态检查脚本

echo "========================================"
echo "飞书Claude Bot - 服务状态"
echo "========================================"
echo ""

# systemd服务状态
echo "【systemd服务】"
if systemctl --user is-active --quiet feishu-bot.service; then
    echo "✅ 服务状态: 运行中"
    systemctl --user status feishu-bot.service --no-pager | head -10
else
    echo "❌ 服务状态: 已停止"
fi
echo ""

# 进程状态
echo "【进程状态】"
WS_COUNT=$(pgrep -f "feishu_websocket_client.py" | wc -l)
BOT_COUNT=$(pgrep -f "feishu_claude_local_bot.py" | wc -l)

echo "WebSocket客户端: $WS_COUNT 个进程"
echo "消息处理器: $BOT_COUNT 个进程"

if [ $WS_COUNT -gt 0 ]; then
    WS_PID=$(pgrep -f "feishu_websocket_client.py" | head -1)
    echo "  PID: $WS_PID"
fi

if [ $BOT_COUNT -gt 0 ]; then
    BOT_PID=$(pgrep -f "feishu_claude_local_bot.py" | head -1)
    echo "  PID: $BOT_PID"
fi
echo ""

# WebSocket连接状态
echo "【WebSocket连接】"
WS_LOG="/home/ian/projects/feishu-claude-bot/logs/websocket.log"
if [ -f "$WS_LOG" ]; then
    if tail -20 "$WS_LOG" | grep -q "connected to"; then
        echo "✅ 已连接到飞书"
        tail -5 "$WS_LOG" | grep "connected" | tail -1
    else
        echo "⚠️  未连接或连接中..."
    fi
else
    echo "❌ 日志文件不存在"
fi
echo ""

# 消息队列状态
echo "【消息队列】"
MSG_FILE="/tmp/feishu_messages.jsonl"
PROC_FILE="/tmp/feishu_processed.jsonl"

if [ -f "$MSG_FILE" ]; then
    MSG_COUNT=$(wc -l < "$MSG_FILE")
    echo "待处理消息: $MSG_COUNT 条"
else
    echo "待处理消息: 0 条"
fi

if [ -f "$PROC_FILE" ]; then
    PROC_COUNT=$(wc -l < "$PROC_FILE")
    echo "已处理消息: $PROC_COUNT 条"
else
    echo "已处理消息: 0 条"
fi
echo ""

echo "========================================"
