#!/bin/bash
# 飞书 Claude Bot 系统管理脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 WebSocket 客户端状态
check_ws_client() {
    if pgrep -f "feishu_websocket_client.py" > /dev/null; then
        local pid=$(pgrep -f 'feishu_websocket_client.py')
        echo -e "${GREEN}✅${NC} WebSocket 客户端运行中 (PID: $pid)"
        
        # 检查连接状态
        if grep -q "connected to wss://" /tmp/feishu-websocket-client.log 2>/dev/null; then
            echo -e "${GREEN}✅${NC} 已连接到飞书"
        else
            echo -e "${YELLOW}⏳${NC} 正在连接..."
        fi
        return 0
    else
        echo -e "${RED}❌${NC} WebSocket 客户端未运行"
        return 1
    fi
}

# 检查 Bot 状态
check_bot() {
    if pgrep -f "feishu_claude_local_bot.py" > /dev/null; then
        local pid=$(pgrep -f 'feishu_claude_local_bot.py')
        echo -e "${GREEN}✅${NC} Bot 消息处理器运行中 (PID: $pid)"
        return 0
    else
        echo -e "${RED}❌${NC} Bot 消息处理器未运行"
        return 1
    fi
}

# 启动所有服务
start_all() {
    echo "=== 启动飞书 Claude Bot 系统 ==="
    echo ""
    
    # 启动 WebSocket 客户端
    echo "启动 WebSocket 客户端..."
    if ! pgrep -f "feishu_websocket_client.py" > /dev/null; then
        nohup python3 -u feishu_websocket_client.py > /tmp/feishu-websocket-client.log 2>&1 &
        sleep 2
        if pgrep -f "feishu_websocket_client.py" > /dev/null; then
            echo -e "${GREEN}✅${NC} WebSocket 客户端已启动"
        else
            echo -e "${RED}❌${NC} WebSocket 客户端启动失败"
            tail -20 /tmp/feishu-websocket-client.log
        fi
    else
        echo -e "${YELLOW}⚠️${NC} WebSocket 客户端已在运行"
    fi
    
    echo ""
    
    # 启动 Bot
    echo "启动 Bot 消息处理器..."
    if ! pgrep -f "feishu_claude_local_bot.py" > /dev/null; then
        nohup python3 -u feishu_claude_local_bot.py > /tmp/feishu-claude-bot-user.log 2>&1 &
        sleep 2
        if pgrep -f "feishu_claude_local_bot.py" > /dev/null; then
            echo -e "${GREEN}✅${NC} Bot 消息处理器已启动"
        else
            echo -e "${RED}❌${NC} Bot 消息处理器启动失败"
        fi
    else
        echo -e "${YELLOW}⚠️${NC} Bot 消息处理器已在运行"
    fi
    
    echo ""
    echo "=== 系统状态 ==="
    status
}

# 停止所有服务
stop_all() {
    echo "=== 停止飞书 Claude Bot 系统 ==="
    echo ""
    
    echo "停止 WebSocket 客户端..."
    pkill -f "feishu_websocket_client.py" && echo -e "${GREEN}✅${NC} WebSocket 客户端已停止" || echo -e "${YELLOW}⚠️${NC} WebSocket 客户端未运行"
    
    echo "停止 Bot 消息处理器..."
    pkill -f "feishu_claude_local_bot.py" && echo -e "${GREEN}✅${NC} Bot 消息处理器已停止" || echo -e "${YELLOW}⚠️${NC} Bot 消息处理器未运行"
}

# 重启所有服务
restart_all() {
    stop_all
    sleep 2
    echo ""
    start_all
}

# 显示状态
status() {
    echo "=== 飞书 Claude Bot 系统状态 ==="
    echo ""
    
    check_ws_client
    check_bot
    
    echo ""
    echo "=== 消息统计 ==="
    echo "总消息数: $(wc -l < /tmp/feishu_messages.jsonl 2>/dev/null || echo 0)"
    echo "已处理数: $(wc -l < /tmp/feishu_processed.jsonl 2>/dev/null || echo 0)"
    echo ""
    
    echo "=== 日志文件 ==="
    echo "WebSocket 客户端: /tmp/feishu-websocket-client.log"
    echo "Bot 消息处理器: /tmp/feishu-claude-bot-user.log"
}

# 查看日志
logs() {
    local service=$1
    case "$service" in
        ws|websocket)
            echo "=== WebSocket 客户端日志 (最近30行) ==="
            tail -30 /tmp/feishu-websocket-client.log
            ;;
        bot)
            echo "=== Bot 消息处理器日志 (最近30行) ==="
            tail -30 /tmp/feishu-claude-bot-user.log
            ;;
        *)
            echo "用法: $0 logs {ws|bot}"
            ;;
    esac
}

# 实时监控日志
follow() {
    local service=$1
    case "$service" in
        ws|websocket)
            echo "=== 实时监控 WebSocket 客户端日志 (Ctrl+C 退出) ==="
            tail -f /tmp/feishu-websocket-client.log
            ;;
        bot)
            echo "=== 实时监控 Bot 消息处理器日志 (Ctrl+C 退出) ==="
            tail -f /tmp/feishu-claude-bot-user.log
            ;;
        *)
            echo "用法: $0 follow {ws|bot}"
            ;;
    esac
}

# 主命令处理
case "$1" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    restart)
        restart_all
        ;;
    status)
        status
        ;;
    logs)
        logs "$2"
        ;;
    follow)
        follow "$2"
        ;;
    *)
        echo "飞书 Claude Bot 系统管理"
        echo ""
        echo "用法: $0 {start|stop|restart|status|logs|follow}"
        echo ""
        echo "命令说明："
        echo "  start         - 启动所有服务"
        echo "  stop          - 停止所有服务"
        echo "  restart       - 重启所有服务"
        echo "  status        - 查看系统状态"
        echo "  logs {ws|bot} - 查看日志"
        echo "  follow {ws|bot} - 实时监控日志"
        echo ""
        echo "示例："
        echo "  $0 status          # 查看状态"
        echo "  $0 logs ws         # 查看 WebSocket 客户端日志"
        echo "  $0 follow bot      # 实时监控 Bot 日志"
        exit 1
        ;;
esac
