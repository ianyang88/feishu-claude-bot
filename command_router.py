#!/usr/bin/env python3
"""
命令路由器

根据用户模式将消息路由到正确的处理器（Shell 或 Claude）
"""

from typing import Dict, Tuple
from session_manager import SessionManager
from shell_executor import ShellExecutor
from project_manager import ProjectManager


class CommandRouter:
    """命令路由器

    管理用户模式（Shell/Claude），将消息路由到对应的处理器
    """

    # 用户模式
    MODE_SHELL = "shell"
    MODE_CLAUDE = "claude"

    def __init__(self, claude_cli_path: str, default_working_dir: str):
        """初始化命令路由器

        Args:
            claude_cli_path: Claude CLI可执行文件路径
            default_working_dir: 默认工作目录
        """
        self.claude_cli_path = claude_cli_path
        self.default_working_dir = default_working_dir

        # 初始化组件
        self.session_manager = SessionManager()
        self.shell_executor = ShellExecutor(default_working_dir)
        self.project_manager = ProjectManager()

        # 用户状态: chat_id -> mode
        self.user_modes: Dict[str, str] = {}

    def get_mode(self, chat_id: str) -> str:
        """获取用户当前模式

        Args:
            chat_id: 飞书聊天ID

        Returns:
            用户模式（"shell" 或 "claude"）
        """
        return self.user_modes.get(chat_id, self.MODE_SHELL)

    def set_mode(self, chat_id: str, mode: str):
        """设置用户模式

        Args:
            chat_id: 飞书聊天ID
            mode: 目标模式（"shell" 或 "claude"）
        """
        self.user_modes[chat_id] = mode
        print(f"[CommandRouter] 用户 {chat_id} 模式切换为: {mode}")

    def route(self, chat_id: str, sender_id: str, message: str) -> Tuple[str, str]:
        """路由消息到正确的处理器

        Args:
            chat_id: 飞书聊天ID
            sender_id: 发送者ID
            message: 消息内容

        Returns:
            (response_type, content)
            response_type: "shell" | "claude" | "system" | "error"
        """
        mode = self.get_mode(chat_id)
        message = message.strip()

        print(f"[CommandRouter] 路由消息: mode={mode}, message={message[:50]}...")

        # ========== 全局命令 ==========
        if message == "/help":
            return "system", self._get_help()

        # ========== Claude 模式 ==========
        if mode == self.MODE_CLAUDE:
            return self._route_claude_mode(chat_id, message)

        # ========== Shell 模式 ==========
        else:  # mode == self.MODE_SHELL
            return self._route_shell_mode(chat_id, message)

    def _route_claude_mode(self, chat_id: str, message: str) -> Tuple[str, str]:
        """路由Claude模式的消息"""
        # 退出Claude模式
        # 退出Claude模式
        if message in ["exit", "quit", "q"]:
            self.session_manager.close_session(chat_id)
            self.set_mode(chat_id, self.MODE_SHELL)
            return "system", "已退出 Claude 模式，返回 Shell"

        # 所有消息（包括 /xxx 命令）都发送给Claude
        session = self.session_manager.get_session(chat_id)
        if session and session.is_alive():
            response = session.send_message(message, timeout=300)
            if response:
                return "claude", response
            return "error", "❌ Claude响应超时或失败"

        return "error", "❌ Claude会话未激活，发送 `claude` 进入会话"

    def _route_shell_mode(self, chat_id: str, message: str) -> Tuple[str, str]:
        """路由Shell模式的消息"""
        # 进入Claude模式
        if message == "claude":
            self.set_mode(chat_id, self.MODE_CLAUDE)
            working_dir = self.shell_executor.get_working_dir(chat_id)

            # 创建或获取会话
            session = self.session_manager.get_or_create_session(
                chat_id, self.claude_cli_path, working_dir
            )

            return "system", "✅ 已进入 Claude 模式\n\n发送消息开始对话，`exit` 退出"

        # 项目管理命令
        if message in ["projects", "proj", "项目"]:
            current_dir = self.shell_executor.get_working_dir(chat_id)
            return "shell", self.project_manager.format_list(current_path=current_dir)

        # use 命令 - 切换项目
        if message.startswith("use "):
            project_name = message[4:].strip()
            project = self.project_manager.get(project_name)
            if not project:
                # 尝试搜索
                results = self.project_manager.search(project_name)
                if results:
                    if len(results) == 1:
                        project = results[0]
                    else:
                        return "shell", f"❌ 找到多个匹配的项目：\n\n{self.project_manager.format_list(results)}"
                else:
                    return "shell", f"❌ 项目不存在：{project_name}\n\n使用 `projects` 查看所有项目"

            success, path = self.shell_executor.set_working_dir(chat_id, project.path)
            if success:
                return "shell", f"✅ 已切换到项目：{project.name}\n📁 {path}\n\n描述：{project.description or '无描述'}"
            return "shell", f"❌ {path}"

        # search 命令 - 搜索项目
        if message.startswith("search "):
            keyword = message[7:].strip()
            results = self.project_manager.search(keyword)
            if not results:
                return "shell", f"❌ 没有找到匹配 '{keyword}' 的项目"
            return "shell", self.project_manager.format_list(results)

        # cd 命令 - 切换目录
        if message.startswith("cd "):
            path = message[3:].strip()
            success, result = self.shell_executor.set_working_dir(chat_id, path)
            return "shell", result if success else f"❌ {result}"

        # pwd 命令 - 显示当前目录
        if message == "pwd":
            return "shell", self.shell_executor.get_current_dir_display(chat_id)

        # ls 命令 - 列出目录
        if message.startswith("ls"):
            parts = message.split(maxsplit=1)
            path = parts[1] if len(parts) > 1 else None
            success, result = self.shell_executor.list_directory(chat_id, path)
            return "shell", result if success else f"❌ {result}"

        # mkdir 命令 - 创建目录
        if message.startswith("mkdir "):
            path = message[6:].strip()
            success, result = self.shell_executor.make_directory(chat_id, path)
            return "shell", result

        # 其他命令 - 作为shell命令执行
        output = self.shell_executor.execute(chat_id, message)
        return "shell", output

    def _get_help(self) -> str:
        """获取帮助信息"""
        return """🤖 飞书Claude Bot - 远程Shell模式

📁 Shell 模式（默认）:
  ls [path]              列出目录内容
  cd <path>              切换工作目录
  pwd                    显示当前工作目录
  mkdir <path>           创建新目录
  <任何shell命令>        执行并返回结果
  claude                 进入Claude交互模式

📋 项目管理:
  projects / proj        列出所有项目
  use <项目名>           切换到指定项目
  search <关键词>        搜索项目

🤖 Claude 模式:
  普通文字               与Claude对话
  /xxx                   Claude命令（如 /brainstorming）
  exit                   退出Claude模式

💡 使用示例:
  ls                     列出当前目录
  cd ~/projects          切换到项目目录
  projects               查看所有项目
  use openclaw           切换到openclaw项目
  claude                 进入Claude对话
  """

    def cleanup(self, chat_id: str = None):
        """清理资源

        Args:
            chat_id: 指定聊天ID，None表示清理所有
        """
        if chat_id:
            self.session_manager.close_session(chat_id)
            if chat_id in self.user_modes:
                del self.user_modes[chat_id]
        else:
            self.session_manager.close_all_sessions()
            self.user_modes.clear()

    def get_stats(self) -> dict:
        """获取统计信息

        Returns:
            包含统计信息的字典
        """
        return {
            "active_sessions": self.session_manager.get_session_count(),
            "user_modes": len(self.user_modes),
            "shell_dirs": len(self.shell_executor.chat_working_dirs),
        }
