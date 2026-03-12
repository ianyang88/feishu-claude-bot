#!/usr/bin/env python3
"""
会话管理器

管理多个用户的Claude会话，支持创建、获取、关闭会话
"""

from typing import Dict, Optional
from claude_session import ClaudeSession


class SessionManager:
    """管理所有用户的Claude会话

    每个聊天ID (chat_id) 可以有一个活跃的Claude会话
    """

    def __init__(self):
        """初始化会话管理器"""
        # chat_id -> ClaudeSession
        self.active_sessions: Dict[str, ClaudeSession] = {}

    def get_or_create_session(self, chat_id: str, cli_path: str,
                              working_dir: str, session_id: str = None) -> ClaudeSession:
        """获取或创建Claude会话

        Args:
            chat_id: 飞书聊天ID
            cli_path: Claude CLI可执行文件路径
            working_dir: 工作目录
            session_id: Claude会话ID（可选，用于恢复现有会话）

        Returns:
            ClaudeSession实例
        """
        # 如果会话已存在且存活，直接返回
        if chat_id in self.active_sessions:
            session = self.active_sessions[chat_id]
            if session.is_alive():
                print(f"[SessionManager] 复用现有会话: {chat_id}")
                return session
            else:
                # 会话已死亡，清理
                print(f"[SessionManager] 清理已死亡会话: {chat_id}")
                del self.active_sessions[chat_id]

        # 创建新会话
        print(f"[SessionManager] 创建新会话: {chat_id}")
        session = ClaudeSession(cli_path, working_dir, session_id)
        self.active_sessions[chat_id] = session
        return session

    def get_session(self, chat_id: str) -> Optional[ClaudeSession]:
        """获取指定chat_id的会话（不创建）

        Args:
            chat_id: 飞书聊天ID

        Returns:
            ClaudeSession实例，不存在返回None
        """
        return self.active_sessions.get(chat_id)

    def close_session(self, chat_id: str) -> bool:
        """关闭指定chat_id的会话

        Args:
            chat_id: 飞书聊天ID

        Returns:
            成功返回True，失败返回False
        """
        if chat_id not in self.active_sessions:
            return False

        session = self.active_sessions[chat_id]
        session.close()
        del self.active_sessions[chat_id]

        print(f"[SessionManager] 已关闭会话: {chat_id}")
        return True

    def close_all_sessions(self):
        """关闭所有活跃会话"""
        for chat_id in list(self.active_sessions.keys()):
            self.close_session(chat_id)

    def session_exists(self, chat_id: str) -> bool:
        """检查指定chat_id是否有活跃会话

        Args:
            chat_id: 飞书聊天ID

        Returns:
            存在且存活返回True，否则返回False
        """
        if chat_id not in self.active_sessions:
            return False

        return self.active_sessions[chat_id].is_alive()

    def list_active_chats(self) -> list:
        """列出所有有活跃会话的聊天ID

        Returns:
            聊天ID列表
        """
        return list(self.active_sessions.keys())

    def get_session_count(self) -> int:
        """获取当前活跃会话数量

        Returns:
            活跃会话数量
        """
        return len(self.active_sessions)

    def cleanup_dead_sessions(self):
        """清理已死亡的会话"""
        dead_chats = []
        for chat_id, session in self.active_sessions.items():
            if not session.is_alive():
                dead_chats.append(chat_id)

        for chat_id in dead_chats:
            print(f"[SessionManager] 清理已死亡会话: {chat_id}")
            del self.active_sessions[chat_id]

        return len(dead_chats)
