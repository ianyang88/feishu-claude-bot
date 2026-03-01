#!/bin/bash
# 飞书Claude Bot 启动脚本

PROJECT_DIR="/home/ian/projects/feishu-claude-bot"
LOG_DIR="$PROJECT_DIR/logs"
WS_LOG="$LOG_DIR/websocket.log"
BOT_LOG="$LOG_DIR/bot.log"

# 清理之前的消息队列
rm -f /tmp/feishu_messages.jsonl /tmp/feishu_processed.jsonl

# 启动WebSocket客户端
echo "[$(date)] 启动WebSocket客户端..." >> "$WS_LOG"
python3 -u "$PROJECT_DIR/feishu_websocket_client.py" >> "$WS_LOG" 2>&1 &
WS_PID=$!
echo "[$(date)] WebSocket客户端 PID: $WS_PID" >> "$WS_LOG"

# 启动消息处理器
echo "[$(date)] 启动消息处理器..." >> "$BOT_LOG"
python3 -u "$PROJECT_DIR/feishu_claude_local_bot.py" >> "$BOT_LOG" 2>&1 &
BOT_PID=$!
echo "[$(date)] 消息处理器 PID: $BOT_PID" >> "$BOT_LOG"

# 等待进程
wait $WS_PID $BOT_PID
