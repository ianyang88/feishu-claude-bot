#!/usr/bin/env python3
"""
Shell命令执行器

执行shell命令并管理每个聊天的工作目录
"""

import os
import subprocess
from typing import Dict, Tuple


class ShellExecutor:
    """Shell命令执行器

    为每个聊天维护独立的工作目录，支持执行shell命令
    """

    def __init__(self, default_working_dir: str):
        """初始化Shell执行器

        Args:
            default_working_dir: 默认工作目录
        """
        self.default_working_dir = os.path.expanduser(default_working_dir)
        # chat_id -> working_dir
        self.chat_working_dirs: Dict[str, str] = {}

    def get_working_dir(self, chat_id: str) -> str:
        """获取指定聊天的工作目录

        Args:
            chat_id: 飞书聊天ID

        Returns:
            工作目录路径
        """
        return self.chat_working_dirs.get(chat_id, self.default_working_dir)

    def set_working_dir(self, chat_id: str, path: str) -> Tuple[bool, str]:
        """设置指定聊天的工作目录

        Args:
            chat_id: 飞书聊天ID
            path: 目标路径

        Returns:
            (成功, 消息) 成功时返回True和完整路径，失败返回False和错误消息
        """
        # 展开波浪号
        expanded_path = os.path.expanduser(path)

        # 转换为绝对路径
        if not os.path.isabs(expanded_path):
            current_dir = self.get_working_dir(chat_id)
            expanded_path = os.path.abspath(os.path.join(current_dir, expanded_path))

        # 验证目录存在
        if not os.path.isdir(expanded_path):
            return False, f"目录不存在: {expanded_path}"

        # 验证可访问权限
        if not os.access(expanded_path, os.R_OK | os.X_OK):
            return False, f"无权限访问目录: {expanded_path}"

        # 保存工作目录
        self.chat_working_dirs[chat_id] = expanded_path
        return True, expanded_path

    def execute(self, chat_id: str, command: str, timeout: int = 30) -> str:
        """执行shell命令

        Args:
            chat_id: 飞书聊天ID
            command: 要执行的命令
            timeout: 超时时间（秒）

        Returns:
            命令输出（stdout或stderr）
        """
        working_dir = self.get_working_dir(chat_id)

        try:
            print(f"[ShellExecutor] 执行命令: {command}")
            print(f"[ShellExecutor] 工作目录: {working_dir}")

            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            # 优先返回stdout，如果为空则返回stderr
            if result.stdout:
                output = result.stdout
                print(f"[ShellExecutor] stdout: {len(output)} 字符")
            else:
                output = result.stderr
                print(f"[ShellExecutor] stderr: {len(output)} 字符")

            return output

        except subprocess.TimeoutExpired:
            error_msg = f"命令执行超时（{timeout}秒）"
            print(f"[ShellExecutor] {error_msg}")
            return error_msg

        except Exception as e:
            error_msg = f"执行失败: {str(e)}"
            print(f"[ShellExecutor] {error_msg}")
            return error_msg

    def resolve_path(self, chat_id: str, path: str) -> str:
        """解析路径（展开波浪号、转换为绝对路径）

        Args:
            chat_id: 飞书聊天ID
            path: 要解析的路径

        Returns:
            解析后的绝对路径
        """
        expanded = os.path.expanduser(path)

        if not os.path.isabs(expanded):
            current_dir = self.get_working_dir(chat_id)
            expanded = os.path.abspath(os.path.join(current_dir, expanded))

        return expanded

    def list_directory(self, chat_id: str, path: str = None) -> Tuple[bool, str]:
        """列出目录内容（便捷方法）

        Args:
            chat_id: 飞书聊天ID
            path: 要列出的路径，None表示当前工作目录

        Returns:
            (成功, 结果) 成功时返回True和目录内容，失败返回False和错误消息
        """
        target_path = path if path else self.get_working_dir(chat_id)

        # 解析路径
        target_path = self.resolve_path(chat_id, target_path)

        # 验证路径存在
        if not os.path.exists(target_path):
            return False, f"路径不存在: {target_path}"

        # 如果是文件，显示文件信息
        if os.path.isfile(target_path):
            return True, f"📄 {target_path}"

        # 列出目录内容
        try:
            entries = os.listdir(target_path)
            if not entries:
                return True, f"📁 {target_path}\n(空目录)"

            # 分类显示
            dirs = []
            files = []
            for entry in sorted(entries):
                full_path = os.path.join(target_path, entry)
                if os.path.isdir(full_path):
                    dirs.append(f"📁 {entry}/")
                else:
                    files.append(f"📄 {entry}")

            result = f"📁 {target_path}\n\n"
            if dirs:
                result += "目录：\n" + "\n".join(dirs) + "\n\n"
            if files:
                result += "文件：\n" + "\n".join(files)

            return True, result

        except PermissionError:
            return False, f"无权限访问: {target_path}"
        except Exception as e:
            return False, f"列出目录失败: {str(e)}"

    def make_directory(self, chat_id: str, path: str) -> Tuple[bool, str]:
        """创建目录（便捷方法）

        Args:
            chat_id: 飞书聊天ID
            path: 要创建的目录路径

        Returns:
            (成功, 消息)
        """
        dir_path = self.resolve_path(chat_id, path)

        # 检查是否已存在
        if os.path.exists(dir_path):
            return False, f"路径已存在: {dir_path}"

        # 检查父目录权限
        parent_dir = os.path.dirname(dir_path)
        if parent_dir and not os.access(parent_dir, os.W_OK):
            return False, f"无权限在 {parent_dir} 中创建目录"

        # 创建目录
        try:
            os.makedirs(dir_path, exist_ok=False)
            return True, f"✅ 目录已创建: {dir_path}"
        except Exception as e:
            return False, f"创建目录失败: {str(e)}"

    def get_current_dir_display(self, chat_id: str) -> str:
        """获取当前工作目录的显示文本（便捷方法）

        Args:
            chat_id: 飞书聊天ID

        Returns:
            格式化的工作目录显示文本
        """
        working_dir = self.get_working_dir(chat_id)
        return f"📁 当前工作目录: {working_dir}"
