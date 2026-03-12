# 远程Shell架构设计文档

**日期**: 2026-03-12
**作者**: Ian + Claude
**状态**: 设计完成，待实现

---

## 概述

将飞书Bot从"单次Claude调用模式"改造为"远程Shell + 持久Claude会话模式"。

### 核心变化

| 当前模式 | 新模式 |
|---------|--------|
| 所有消息发送给Claude | Shell模式执行命令，Claude模式持久对话 |
| 每次`--print`单次调用 | 持久进程保持连接 |
| 历史通过提示词拼接 | 真正的会话持久化 |
| `/` 开头为Bot命令 | `/claude`进入Claude，其他为Shell命令 |

---

## 系统架构

### 状态机图

```
┌──────────────────┐              ┌──────────────────┐
│   Shell Mode     │    /claude    │   Claude Mode    │
│   (默认状态)      │  ──────────→  │   (交互式会话)    │
│                  │               │                  │
│  ls, cd, pwd     │  ←────────    │  持久连接到       │
│  任何shell命令   │    /exit      │  Claude CLI      │
│  /claude         │               │                  │
│  /help           │               │  /switch <会话>   │
└──────────────────┘               │  /sessions       │
                                   │  /new            │
                                   │  /exit           │
                                   └──────────────────┘
```

### 会话隔离

```
(chat_id, mode) 组合维护状态

chat_id="oc_abc123", mode="shell"  → Shell会话
chat_id="oc_abc123", mode="claude" → Claude会话(独立进程)
chat_id="oc_def456", mode="shell"  → 另一个用户的Shell会话
```

---

## 核心组件

### 1. ClaudeSession - 持久会话管理

```python
class ClaudeSession:
    """Claude CLI 交互式会话"""

    def __init__(self, cli_path: str, working_dir: str, session_id: str = None):
        self.cli_path = cli_path
        self.working_dir = working_dir
        self.session_id = session_id

        # 启动持久进程（不用--print）
        self.process = subprocess.Popen(
            [cli_path] + (["--session", session_id] if session_id else []),
            cwd=working_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def send_message(self, message: str, timeout: int = 120) -> Optional[str]:
        """发送消息到持久进程并等待响应"""
        self.process.stdin.write(message + "\n")
        self.process.stdin.flush()

        # 读取直到检测到输出结束
        response_lines = []
        while True:
            line = self.process.stdout.readline()
            if not line or self._is_response_complete(response_lines):
                break
            response_lines.append(line.rstrip())

        return "\n".join(response_lines)

    def switch_session(self, session_id: str) -> bool:
        """切换Claude会话"""
        self.send_message(f"/switch {session_id}")
        self.session_id = session_id
        return True

    def list_sessions(self) -> list:
        """列出所有会话"""
        response = self.send_message("/sessions")
        return self._parse_sessions(response)

    def close(self):
        """关闭进程"""
        self.process.stdin.write("/exit\n")
        self.process.stdin.flush()
        self.process.wait()
```

### 2. SessionManager - 多用户会话管理

```python
class SessionManager:
    """管理所有用户的Claude会话"""

    def __init__(self):
        self.active_sessions: Dict[str, ClaudeSession] = {}

    def get_or_create_session(self, chat_id: str, cli_path: str,
                              working_dir: str, session_id: str = None) -> ClaudeSession:
        """获取或创建会话"""
        if chat_id not in self.active_sessions:
            self.active_sessions[chat_id] = ClaudeSession(
                cli_path, working_dir, session_id
            )
        return self.active_sessions[chat_id]

    def close_session(self, chat_id: str):
        """关闭会话"""
        if chat_id in self.active_sessions:
            self.active_sessions[chat_id].close()
            del self.active_sessions[chat_id]
```

### 3. ShellExecutor - Shell命令执行

```python
class ShellExecutor:
    """Shell命令执行器"""

    def __init__(self, default_working_dir: str):
        self.default_working_dir = default_working_dir
        self.chat_working_dirs: Dict[str, str] = {}

    def get_working_dir(self, chat_id: str) -> str:
        return self.chat_working_dirs.get(chat_id, self.default_working_dir)

    def set_working_dir(self, chat_id: str, path: str) -> tuple[bool, str]:
        expanded = os.path.expanduser(path)
        if not os.path.isabs(expanded):
            current = self.get_working_dir(chat_id)
            expanded = os.path.abspath(os.path.join(current, expanded))

        if os.path.isdir(expanded):
            self.chat_working_dirs[chat_id] = expanded
            return True, expanded
        return False, f"目录不存在: {path}"

    def execute(self, chat_id: str, command: str, timeout: int = 30) -> str:
        """执行shell命令"""
        working_dir = self.get_working_dir(chat_id)
        result = subprocess.run(
            command, shell=True, cwd=working_dir,
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout if result.stdout else result.stderr
```

### 4. CommandRouter - 命令路由

```python
class CommandRouter:
    """命令路由器"""

    def __init__(self):
        self.shell_executor = ShellExecutor(WORKING_DIR)
        self.session_manager = SessionManager()
        self.user_modes: Dict[str, str] = {}  # chat_id -> "shell" | "claude"

    def route(self, chat_id: str, sender_id: str, message: str) -> tuple[str, str]:
        """路由消息到正确的处理器"""
        mode = self.user_modes.get(chat_id, "shell")
        message = message.strip()

        # 全局命令
        if message == "/help":
            return "system", self._get_help()

        # Claude 模式
        if mode == "claude":
            if message in ["/exit", "exit"]:
                self.session_manager.close_session(chat_id)
                self.user_modes[chat_id] = "shell"
                return "system", "已退出 Claude 模式"

            if message.startswith("/switch "):
                session = self.session_manager.active_sessions.get(chat_id)
                if session:
                    session.switch_session(message[8:].strip())
                    return "system", f"已切换会话"
                return "error", "无活跃会话"

            if message == "/sessions":
                session = self.session_manager.active_sessions.get(chat_id)
                if session:
                    return "system", "\n".join(session.list_sessions())
                return "error", "无活跃会话"

            if message == "/new":
                self.session_manager.close_session(chat_id)
                self.session_manager.get_or_create_session(chat_id, ...)
                return "system", "已创建新会话"

            # 发送给Claude
            session = self.session_manager.active_sessions.get(chat_id)
            if session:
                response = session.send_message(message)
                return "claude", response
            return "error", "会话未激活"

        # Shell 模式
        else:
            if message in ["/claude", "claude"]:
                self.user_modes[chat_id] = "claude"
                self.session_manager.get_or_create_session(chat_id, ...)
                return "system", "已进入 Claude 模式"

            if message.startswith("cd "):
                success, result = self.shell_executor.set_working_dir(
                    chat_id, message[3:].strip()
                )
                return "shell", result if success else f"❌ {result}"

            output = self.shell_executor.execute(chat_id, message)
            return "shell", output
```

---

## 命令参考

### Shell 模式（默认）

| 命令 | 说明 |
|------|------|
| `ls` | 列出文件 |
| `cd <path>` | 切换目录 |
| `pwd` | 显示当前目录 |
| `任何shell命令` | 执行并返回结果 |
| `/claude` | 进入Claude模式 |
| `/help` | 显示帮助 |

### Claude 模式

| 命令 | 说明 |
|------|------|
| `任何消息` | 发送给Claude |
| `/switch <id>` | 切换会话 |
| `/sessions` | 列出所有会话 |
| `/new` | 创建新会话 |
| `/exit` | 返回Shell模式 |

---

## 数据流图

```
用户发送 "ls"
    ↓
CommandRouter.route()
    ↓ (mode=shell)
ShellExecutor.execute("ls")
    ↓
返回文件列表
    ↓
FeishuClient.send_message()

---

用户发送 "/claude"
    ↓
CommandRouter.route()
    ↓ (设置mode=claude)
SessionManager.get_or_create_session()
    ↓
启动Claude CLI进程
    ↓
返回 "已进入 Claude 模式"

---

用户发送 "帮我写个函数" (在Claude模式)
    ↓
CommandRouter.route()
    ↓ (mode=claude)
ClaudeSession.send_message()
    ↓
写入进程stdin → Claude CLI
    ↓
读取stdout ← Claude CLI
    ↓
返回Claude回复
    ↓
FeishuClient.update_card()
```

---

## 安全考虑

1. **Shell注入风险**: 使用 `subprocess.run(shell=True)` 需要谨慎
   - 限制可执行命令白名单
   - 或者用沙箱隔离

2. **会话隔离**: 确保不同 chat_id 的会话完全隔离

3. **进程管理**: Bot重启时需要清理残留的Claude进程

4. **权限控制**: 保留现有的权限检查机制

---

## 待实现清单

- [ ] 实现 `ClaudeSession` 类
- [ ] 实现 `SessionManager` 类
- [ ] 实现 `ShellExecutor` 类
- [ ] 实现 `CommandRouter` 类
- [ ] 重构 `MessageProcessor` 整合新架构
- [ ] 添加进程清理机制（Bot重启时）
- [ ] 更新帮助文档
- [ ] 测试持久会话稳定性
- [ ] 测试模式切换
- [ ] 测试多用户隔离

---

## 兼容性说明

- 保留现有的项目管理命令 (`projects`, `use`, `search` 等)
- 这些命令在Shell模式下仍然有效
- 或者可以考虑迁移到新的命令结构
