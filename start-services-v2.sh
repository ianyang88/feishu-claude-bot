#!/bin/bash
# 飞书Claude Bot V2 启动脚本（远程Shell架构）

PROJECT_DIR="/home/ian/projects/feishu-claude-bot-impl"
LOG_DIR="$PROJECT_DIR/logs"
WS_LOG="$LOG_DIR/websocket.log"
BOT_LOG="$PROJECT_DIR/logs/bot.log"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 清理之前的消息队列（只在首次启动时清理）
if [ ! -f /tmp/feishu_messages.jsonl ]; then
    touch /tmp/feishu_messages.jsonl
fi
if [ ! -f /tmp/feishu_processed.jsonl ]; then
    touch /tmp/feishu_processed.jsonl
fi

# 清理旧进程
OLD_PIDS=$(pgrep -f "feishu_websocket_client|feishu_claude_local_bot" 2>/dev/null || true)
if [ -n "$OLD_PIDS" ]; then
    for pid in $OLD_PIDS; do
        if [ "$pid" != "$$" ]; then
            kill -9 $pid 2>/dev/null
        fi
    done
    sleep 1
fi

# 存储子进程PID
WS_PID=""
BOT_PID=""

# 清理函数
cleanup() {
    echo "[$(date)] 收到停止信号，正在关闭..." >> "$WS_LOG"

    # 先尝试优雅停止
    if [ -n "$WS_PID" ]; then
        kill -TERM $WS_PID 2>/dev/null
    fi
    if [ -n "$BOT_PID" ]; then
        kill -TERM $BOT_PID 2>/dev/null
    fi

    # 等待最多5秒
    for i in {1..10}; do
        if ! kill -0 $WS_PID 2>/dev/null && ! kill -0 $BOT_PID 2>/dev/null; then
            break
        fi
        sleep 0.5
    done

    # 如果进程仍在运行，强制停止
    if [ -n "$WS_PID" ] && kill -0 $WS_PID 2>/dev/null; then
        kill -KILL $WS_PID 2>/dev/null
    fi
    if [ -n "$BOT_PID" ] && kill -0 $BOT_PID 2>/dev/null; then
        kill -KILL $BOT_PID 2>/dev/null
    fi

    echo "[$(date)] 所有进程已停止" >> "$WS_LOG"
    exit 0
}

# 设置信号处理
trap cleanup SIGTERM SIGINT

# 启动WebSocket客户端
echo "[$(date)] 启动WebSocket客户端..." >> "$WS_LOG"
python3 -u "$PROJECT_DIR/feishu_websocket_client.py" >> "$WS_LOG" 2>&1 &
WS_PID=$!
echo "[$(date)] WebSocket客户端 PID: $WS_PID" >> "$WS_LOG"

# 启动消息处理器（V2版本）
echo "[$(date)] 启动消息处理器（V2 - 远程Shell模式）..." >> "$BOT_LOG"
python3 -u "$PROJECT_DIR/feishu_claude_local_bot_v2.py" >> "$BOT_LOG" 2>&1 &
BOT_PID=$!
echo "[$(date)] 消息处理器 PID: $BOT_PID" >> "$BOT_LOG"

# 等待进程
wait $WS_PID $BOT_PID
