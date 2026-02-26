# 飞书 Claude Bot

Claude 本地 CLI 自动化 Bot - 通过飞书与本地 Claude CLI 交互

## 项目结构

```
feishu-claude-bot/
├── feishu_claude_local_bot.py      # Bot 主程序
├── feishu_claude_local_bot.py.backup # 备份文件
├── bot-service.sh                   # 服务管理脚本
├── README.md                        # 项目说明
├── QUICKSTART.md                    # 快速开始
├── SETUP-FEISHU.md                  # 飞书配置指南
├── HOW-TO-GET-ID.md                 # 获取 ID 指南
├── SERVICE-GUIDE.md                 # 服务管理指南
└── .env.example                     # 环境变量示例
```

## 快速使用

### 服务管理

```bash
# 启动服务
./bot-service.sh start

# 停止服务
./bot-service.sh stop

# 重启服务
./bot-service.sh restart

# 查看状态
./bot-service.sh status

# 查看日志
./bot-service.sh logs

# 实时监控日志
./bot-service.sh follow
```

### 飞书命令

在飞书中发送以下命令：

| 命令 | 功能 | 示例 |
|------|------|------|
| `cd <path>` | 切换工作目录 | `cd ~/projects`, `cd ..` |
| `pwd` | 显示当前工作目录 | `pwd` |
| `ls [path]` | 列出目录内容 | `ls`, `ls /tmp` |
| `help` | 显示帮助信息 | `help` |

## 项目根目录

所有项目统一存放在 `~/projects` 目录下，Bot 默认工作目录为 `/home/ian/projects`

## 系统服务

- **Service 文件**: `~/.config/systemd/user/feishu-claude-bot.service`
- **日志文件**: `/tmp/feishu-claude-bot-user.log`
- **开机自启**: 已启用

## 版本历史

- **2026-02-24**: 迁移到 ~/projects/feishu-claude-bot，添加多工作目录支持
