# 项目管理功能使用指南

## 概述

飞书 Claude Bot 现在支持**多项目快速切换**功能，可以方便地在不同项目之间切换，无需每次输入完整路径。

## 功能特性

- ✅ 自动扫描 `~/projects` 目录下的项目
- ✅ 项目别名支持，快速切换
- ✅ 项目搜索功能
- ✅ 持久化存储项目配置

## 可用命令

### 1. 查看所有项目

```
projects
proj
项目
```

显示所有已配置的项目列表，当前项目会用 📍 标记。

### 2. 切换到项目

```
use <项目名或别名>
```

**示例：**
```
use feishu-claude-bot    # 使用完整名称
use fcb                 # 使用别名
use openclaw            # 切换到 openclaw 项目
```

### 3. 搜索项目

```
search <关键词>
```

**示例：**
```
search bot              # 搜索包含 "bot" 的项目
search claude           # 搜索包含 "claude" 的项目
```

### 4. 添加项目

```
addproj <名称> <路径> [别名...]
```

**示例：**
```
addproj myapp ~/projects/my-app
addproj myapp ~/projects/my-app app ma    # 带别名
```

### 5. 删除项目

```
delproj <项目名>
```

**示例：**
```
delproj myapp
```

## 项目配置

### 配置文件位置

`~/.claude/projects.json`

### 配置格式

```json
{
  "projects": {
    "项目名称": {
      "path": "/path/to/project",
      "alias": ["别名1", "别名2"],
      "description": "项目描述"
    }
  }
}
```

### 自动识别项目

项目管理器会自动扫描 `~/projects` 目录，识别包含以下特征的目录作为项目：
- `.git` 目录
- `package.json` (Node.js)
- `pyproject.toml` (Python)
- `Cargo.toml` (Rust)
- `go.mod` (Go)

## 使用场景

### 场景 1：快速切换项目

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

### 场景 2：搜索项目

```
你: search bot
Bot: 📁 项目列表：
     1. **feishu-claude-bot** (fcb, feishu)
        路径: `/home/ian/projects/feishu-claude-bot`
        描述: 项目: feishu-claude-bot
```

### 场景 3：添加新项目

```
you: addproj myapi ~/projects/my-api
Bot: ✅ 项目已添加：myapi

you: use myapi
Bot: ✅ 已切换到项目：myapi
     ✅ 工作目录已切换到：/home/ian/projects/my-api
```

## 项目别名

每个项目可以有多个别名，方便快速切换：

```
项目名: feishu-claude-bot
别名: fcb, feishu

可以使用以下方式切换：
- use feishu-claude-bot  # 完整名称
- use fcb               # 首字母缩写
- use feishu            # 简短形式
```

## 注意事项

1. **项目名称唯一**：项目名称必须唯一，但别名可以重复
2. **自动保存**：所有更改会自动保存到配置文件
3. **持久化**：每个聊天的项目切换是独立的，互不影响
4. **兼容性**：原有的 `cd` 命令仍然可用

## 完整命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `projects` | 列出所有项目 | `projects` |
| `use <项目>` | 切换到项目 | `use openclaw` |
| `search <关键词>` | 搜索项目 | `search bot` |
| `addproj <名称> <路径>` | 添加项目 | `addproj myapp ~/projects/my-app` |
| `delproj <项目名>` | 删除项目 | `delproj myapp` |
| `cd <路径>` | 切换目录 | `cd ~/projects` |
| `pwd` | 显示当前目录 | `pwd` |
| `ls [路径]` | 列出目录 | `ls` |
| `help` | 显示帮助 | `help` |
