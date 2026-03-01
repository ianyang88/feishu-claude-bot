# 飞书 Claude Bot

Claude 本地 CLI 自动化 Bot - 通过飞书与本地 Claude CLI 交互

## 项目结构

```
feishu-claude-bot/
├── feishu_claude_local_bot.py      # Bot 主程序
├── feishu_websocket_client.py      # 飞书 WebSocket 客户端
├── project_manager.py               # 项目管理器
├── manage.sh                        # 统一管理脚本
├── bot-service.sh                   # 服务管理脚本
├── README.md                        # 项目说明
├── PROJECT-MANAGEMENT.md            # 项目管理功能指南
├── QUICKSTART.md                    # 快速开始
├── SETUP-FEISHU.md                  # 飞书配置指南
├── HOW-TO-GET-ID.md                 # 获取 ID 指南
├── SERVICE-GUIDE.md                 # 服务管理指南
└── .env.example                     # 环境变量示例
```

## 快速使用

### 系统管理

```bash
# 查看系统状态
./manage.sh status

# 重启所有服务
./manage.sh restart

# 查看日志
./manage.sh logs ws    # WebSocket 客户端日志
./manage.sh logs bot   # Bot 日志

# 实时监控
./manage.sh follow ws  # 实时监控 WebSocket 日志
./manage.sh follow bot # 实时监控 Bot 日志
```

### 飞书命令

#### 项目管理（新功能）

| 命令 | 功能 | 示例 |
|------|------|------|
| `projects` / `proj` | 列出所有项目 | `projects` |
| `use <项目名>` | 切换到指定项目 | `use openclaw`, `use fcb` |
| `search <关键词>` | 搜索项目 | `search bot` |
| `addproj <名称> <路径>` | 添加新项目 | `addproj myapp ~/projects/my-app` |
| `delproj <项目名>` | 删除项目 | `delproj myapp` |

#### 目录管理

| 命令 | 功能 | 示例 |
|------|------|------|
| `cd <path>` | 切换工作目录 | `cd ~/projects`, `cd ..` |
| `pwd` | 显示当前工作目录 | `pwd` |
| `ls [path]` | 列出目录内容 | `ls`, `ls /tmp` |
| `mkdir <path>` | 创建新目录 | `mkdir new-project` |
| `help` | 显示帮助信息 | `help` |

## 项目管理功能

### 快速切换项目

```
你: projects
Bot: 📁 项目列表：
     1. **feishu-claude-bot** (fcb, feishu) 📍 *当前*
        路径: `/home/ian/projects/feishu-claude-bot`
        描述: 项目: feishu-claude-bot

你: use openclaw
Bot: ✅ 已切换到项目：openclaw
     ✅ 工作目录已切换到：/home/ian/projects/openclaw
```

### 项目配置

- **配置文件**: `~/.claude/projects.json`
- **自动扫描**: 自动识别 `~/projects` 目录下的 Git 项目
- **项目别名**: 支持为项目设置多个别名，方便快速切换

详细使用说明请查看 [PROJECT-MANAGEMENT.md](PROJECT-MANAGEMENT.md)

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  飞书平台                                                    │
└────────────────────────┬────────────────────────────────────┘
                         │ WebSocket
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  feishu_websocket_client.py (飞书 WebSocket 客户端)         │
│  - 连接飞书 WebSocket                                        │
│  - 接收消息并写入 /tmp/feishu_messages.jsonl                │
└────────────────────────┬────────────────────────────────────┘
                         │ 文件读取
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  feishu_claude_local_bot.py (Bot 消息处理器)                │
│  - 监听消息文件                                              │
│  - 项目管理 (project_manager.py)                             │
│  - 调用 Claude CLI                                           │
│  - 发送回复到飞书                                             │
└─────────────────────────────────────────────────────────────┘
```

## 系统服务

- **Service 文件**: `~/.config/systemd/user/feishu-claude-bot.service`
- **日志文件**:
  - `/tmp/feishu-websocket-client.log` (WebSocket 客户端)
  - `/tmp/feishu-claude-bot-user.log` (Bot 消息处理器)
- **开机自启**: 已启用

## 版本历史

- **2026-03-01**: 添加项目管理功能，支持多项目快速切换
- **2026-02-28**: 修复 WebSocket 客户端缺失问题，合并 Windows 和 Linux 项目
- **2026-02-24**: 迁移到 ~/projects/feishu-claude-bot，添加多工作目录支持
