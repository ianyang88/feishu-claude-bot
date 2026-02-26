# 飞书Claude Bot 自动运行配置指南

## ✅ 配置完成

Bot已配置为**systemd用户服务**，具备以下特性：

- ✅ **开机自动启动** - 系统重启后自动运行
- ✅ **崩溃自动重启** - 进程异常退出后自动重启（10秒后）
- ✅ **日志管理** - 统一的日志文件
- ✅ **资源限制** - 内存限制512M，CPU限制50%

---

## 📋 服务管理

### 使用管理脚本（推荐）

```bash
cd /mnt/c/Users/Admin/feishu-mcp-server
./bot-service.sh [命令]
```

#### 可用命令：

| 命令 | 说明 | 示例 |
|------|------|------|
| `start` | 启动服务 | `./bot-service.sh start` |
| `stop` | 停止服务 | `./bot-service.sh stop` |
| `restart` | 重启服务 | `./bot-service.sh restart` |
| `status` | 查看状态 | `./bot-service.sh status` |
| `logs` | 查看日志（50行） | `./bot-service.sh logs` |
| `follow` | 实时监控日志 | `./bot-service.sh follow` |
| `enable` | 启用开机自启 | `./bot-service.sh enable` |
| `disable` | 禁用开机自启 | `./bot-service.sh disable` |

### 使用systemd命令（高级）

```bash
# 启动服务
systemctl --user start feishu-claude-bot.service

# 停止服务
systemctl --user stop feishu-claude-bot.service

# 重启服务
systemctl --user restart feishu-claude-bot.service

# 查看状态
systemctl --user status feishu-claude-bot.service

# 查看日志
journalctl --user -u feishu-claude-bot.service -f

# 启用开机自启
systemctl --user enable feishu-claude-bot.service

# 禁用开机自启
systemctl --user disable feishu-claude-bot.service
```

---

## 📝 日志位置

### Bot运行日志
```bash
# 方法1：使用管理脚本
./bot-service.sh logs
./bot-service.sh follow  # 实时监控

# 方法2：直接查看
tail -f /tmp/feishu-claude-bot-user.log
```

### Systemd日志
```bash
# 查看服务日志
journalctl --user -u feishu-claude-bot.service -f

# 查看最近100条
journalctl --user -u feishu-claude-bot.service -n 100
```

---

## 🔧 服务配置

### 服务文件位置
```
~/.config/systemd/user/feishu-claude-bot.service
```

### 当前配置
- **工作目录**: `/mnt/c/Users/Admin/feishu-mcp-server`
- **执行命令**: `/usr/bin/python3 -u feishu_claude_local_bot.py`
- **内存限制**: 512M
- **CPU限制**: 50%
- **重启策略**: 崩溃后10秒重启
- **开机自启**: 已启用 ✅

### 修改配置

如果需要修改服务配置：

```bash
# 1. 编辑服务文件
nano ~/.config/systemd/user/feishu-claude-bot.service

# 2. 重新加载
systemctl --user daemon-reload

# 3. 重启服务
systemctl --user restart feishu-claude-bot.service
```

---

## 🎯 常用操作

### 日常使用
```bash
# 查看Bot状态
./bot-service.sh status

# 查看实时日志
./bot-service.sh follow

# 重启Bot（如果有问题）
./bot-service.sh restart
```

### 测试变更
```bash
# 1. 停止服务
./bot-service.sh stop

# 2. 手动运行测试
cd /mnt/c/Users/Admin/feishu-mcp-server
python3 -u feishu_claude_local_bot.py

# 3. 测试完成后重新启动服务
./bot-service.sh start
```

---

## 🛠️ 故障排查

### Bot未运行

```bash
# 1. 检查服务状态
./bot-service.sh status

# 2. 查看错误日志
./bot-service.sh logs

# 3. 检查系统日志
journalctl --user -u feishu-claude-bot.service -n 50
```

### Bot频繁重启

```bash
# 查看重启次数和原因
systemctl --user show feishu-claude-bot.service | grep Restart

# 检查内存使用
./bot-service.sh status | grep -i memory
```

### 查看服务配置

```bash
# 显示完整服务配置
systemctl --user cat feishu-claude-bot.service

# 显示服务属性
systemctl --user show feishu-claude-bot.service
```

---

## 📊 监控Bot健康

### 创建健康检查脚本
```bash
# 添加到 crontab -e
# 每分钟检查一次
*/1 * * * * /mnt/c/Users/Admin/feishu-mcp-server/bot-service.sh status > /dev/null || /mnt/c/Users/Admin/feishu-mcp-server/bot-service.sh start
```

---

## 🔐 安全注意事项

1. **权限**: 服务以用户身份运行，不需要root权限
2. **资源限制**: 内存限制512M，防止内存泄漏
3. **日志轮转**: 建议定期清理旧日志

### 清理日志
```bash
# 清理Bot日志
> /tmp/feishu-claude-bot-user.log

# 清理systemd日志（保留最近7天）
journalctl --user --vacuum-time=7d
```

---

## 📚 相关文档

- [README.md](README.md) - 项目主文档
- [QUICKSTART.md](QUICKSTART.md) - 快速开始
- [SETUP-FEISHU.md](SETUP-FEISHU.md) - 飞书设置

---

## ✅ 验证自动运行

### 测试开机自启
```bash
# 1. 确认服务已启用
systemctl --user is-enabled feishu-claude-bot.service
# 应该输出: enabled

# 2. 重启系统后验证
# (实际重启前可以先logout测试)
loginctl terminate-user ian
# 重新登录后检查服务是否自动启动
./bot-service.sh status
```

### 测试崩溃重启
```bash
# 1. 手动杀死进程
pkill -9 feishu_claude_local_bot

# 2. 等待10秒后检查
sleep 12
./bot-service.sh status
# 服务应该自动重启并显示running
```

---

**配置完成！Bot现在会在开机时自动启动，并在崩溃后自动重启。** 🎉
