#!/bin/bash
# 飞书 WebSocket 客户端启动脚本

cd /home/ian/projects/feishu-claude-bot

echo "=== 启动飞书 WebSocket 客户端 ==="
echo ""

# 检查是否已运行
if pgrep -f "feishu_websocket_client.py" > /dev/null; then
    echo "⚠️  WebSocket 客户端已在运行"
    echo "PID: $(pgrep -f 'feishu_websocket_client.py')"
    exit 0
fi

# 启动客户端
nohup python3 -u feishu_websocket_client.py > /tmp/feishu-websocket-client.log 2>&1 &

sleep 2

# 检查是否启动成功
if pgrep -f "feishu_websocket_client.py" > /dev/null; then
    echo "✅ WebSocket 客户端已启动"
    echo "PID: $(pgrep -f 'feishu_websocket_client.py')"
    echo "日志: /tmp/feishu-websocket-client.log"
else
    echo "❌ 启动失败，请检查日志"
    tail -20 /tmp/feishu-websocket-client.log
    exit 1
fi
