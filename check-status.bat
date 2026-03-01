@echo off
echo ========================================
echo 飞书MCP服务 - 状态检查
echo ========================================
echo.

echo 1. 检查Python WebSocket服务...
echo.
tasklist | findstr python.exe
echo.

echo 2. 检查Node.js MCP编译文件...
echo.
if exist "dist\index.js" (
    echo [✓] MCP服务文件存在
) else (
    echo [×] MCP服务文件不存在，请运行: npm run build
)
echo.

echo 3. 检查配置文件...
echo.
if exist ".env" (
    echo [✓] .env 文件存在
) else (
    echo [×] .env 文件不存在
)
echo.

echo 4. 检查消息文件...
echo.
python -c "import os; print('[✓] 消息文件存在' if os.path.exists('/tmp/feishu_messages.jsonl') else print('[×] 消息文件不存在')"
echo.

echo ========================================
echo.
echo 📝 下一步: 配置Claude Desktop
echo.
echo 1. 复制配置文件到:
echo    %%APPDATA%%\Claude\claude_desktop_config.json
echo.
echo 2. 配置内容在 claude_desktop_config.json
echo.
echo 3. 完全重启Claude Desktop
echo.
echo ========================================
echo.
pause
