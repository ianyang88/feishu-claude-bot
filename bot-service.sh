#!/bin/bash
# 飞书Claude Bot 服务管理脚本

case "$1" in
    start)
        echo "启动飞书Claude Bot服务..."
        systemctl --user start feishu-claude-bot.service
        echo "✅ 服务已启动"
        ;;
    stop)
        echo "停止飞书Claude Bot服务..."
        systemctl --user stop feishu-claude-bot.service
        echo "✅ 服务已停止"
        ;;
    restart)
        echo "重启飞书Claude Bot服务..."
        systemctl --user restart feishu-claude-bot.service
        echo "✅ 服务已重启"
        ;;
    status)
        echo "飞书Claude Bot服务状态："
        systemctl --user status feishu-claude-bot.service --no-pager
        ;;
    logs)
        echo "飞书Claude Bot日志（最近50行）："
        tail -50 /tmp/feishu-claude-bot-user.log
        ;;
    follow)
        echo "实时监控飞书Claude Bot日志（Ctrl+C退出）："
        tail -f /tmp/feishu-claude-bot-user.log
        ;;
    enable)
        echo "启用开机自启动..."
        systemctl --user enable feishu-claude-bot.service
        echo "✅ 已启用开机自启动"
        ;;
    disable)
        echo "禁用开机自启动..."
        systemctl --user disable feishu-claude-bot.service
        echo "✅ 已禁用开机自启动"
        ;;
    *)
        echo "飞书Claude Bot 服务管理"
        echo ""
        echo "用法: $0 {start|stop|restart|status|logs|follow|enable|disable}"
        echo ""
        echo "命令说明："
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务"
        echo "  restart - 重启服务"
        echo "  status  - 查看服务状态"
        echo "  logs    - 查看日志（最近50行）"
        echo "  follow  - 实时监控日志"
        echo "  enable  - 启用开机自启动"
        echo "  disable - 禁用开机自启动"
        echo ""
        echo "示例："
        echo "  $0 status    # 查看状态"
        echo "  $0 logs     # 查看日志"
        echo "  $0 follow   # 实时监控"
        exit 1
        ;;
esac
