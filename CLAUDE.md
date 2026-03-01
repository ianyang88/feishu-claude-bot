# 飞书Claude Bot - 项目说明

## 项目概述

这是一个飞书-Claude本地CLI自动化Bot服务，实现以下功能：
- 监听飞书消息
- 自动调用本地Claude CLI处理
- 自动回复飞书

## 项目结构

```
feishu-claude-bot/
├── feishu_claude_local_bot.py   # 主程序 - 消息处理和Claude CLI调用
├── feishu_websocket_client.py   # WebSocket客户端 - 飞书长连接
├── project_manager.py            # 项目管理器 - 多项目快速切换
├── QUICKSTART.md                 # 快速开始指南
├── SETUP-FEISHU.md              # 飞书配置指南
├── HOW-TO-GET-ID.md             # ID获取指南
└── SERVICE-GUIDE.md             # 服务指南
```

## 核心组件

### 1. feishu_claude_local_bot.py
主程序，包含：
- **授权机制**: 四级权限系统（ADMIN, TRUSTED, STANDARD, RESTRICTED）
- **命令系统**: 支持项目管理、目录管理命令
- **消息处理**: 监听、解析、回复飞书消息
- **Claude CLI集成**: 调用本地Claude CLI处理用户消息

### 2. feishu_websocket_client.py
WebSocket客户端，负责：
- 建立飞书长连接
- 接收实时消息事件
- 将消息写入队列文件

### 3. project_manager.py
项目管理器，支持：
- 项目列表展示
- 快速项目切换
- 项目搜索
- 项目添加/删除

## 配置

### 飞书应用配置
```python
FEISHU_APP_ID = "cli_a9103ecc9fb85bd8"
FEISHU_APP_SECRET = "qRyCROVPjtZDjCuZqDNIPdeWteHOnVck"
```

### Claude CLI配置
```python
CLAUDE_CLI_PATH = "/home/ian/.npm-global/bin/claude"
WORKING_DIR = os.path.expanduser("~/projects")
```

## 消息文件路径
- 消息队列: `/tmp/feishu_messages.jsonl`
- 已处理记录: `/tmp/feishu_processed.jsonl`
- 审计日志: `/tmp/feishu_audit.jsonl`

## 控制命令

### 项目管理
- `projects` / `proj` - 列出所有项目
- `use <项目名>` - 切换到指定项目
- `search <关键词>` - 搜索项目
- `addproj <名称> <路径>` - 添加新项目
- `delproj <项目名>` - 删除项目

### 目录管理
- `cd <path>` - 切换工作目录
- `pwd` - 显示当前工作目录
- `ls [path]` - 列出目录内容
- `mkdir <path>` - 创建新目录

## 最近修复 (Git Diff)

1. **新增项目管理命令**: 添加了projects、use、search、addproj、delproj命令
2. **添加超时参数**: 修复requests调用缺少timeout的问题（安全风险）
3. **无效消息处理**: 添加对缺少message_id的消息的跳过逻辑
4. **字段名修复**: 修复WebSocket客户端中msg_type -> message_type

## 调试重点

1. **WebSocket连接**: 确保飞书长连接正常建立
2. **消息接收**: 验证消息能正确写入队列文件
3. **权限检查**: 确认用户权限系统工作正常
4. **Claude CLI调用**: 验证本地Claude CLI能正确响应
5. **消息回复**: 确保回复能正确发送到飞书

## 运行方式

### 启动WebSocket客户端
```bash
python3 feishu_websocket_client.py
```

### 启动消息处理器
```bash
python3 feishu_claude_local_bot.py
```
