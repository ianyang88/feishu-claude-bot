#!/usr/bin/env python3
"""
Claude CLI 会话管理

使用 --print 模式获取纯文本输出
"""

import os
import subprocess
import time
from typing import Optional, List


class ClaudeSession:
    """Claude CLI 会话管理

    使用 --print 模式获取纯文本输出
    """

    def __init__(self, cli_path: str, working_dir: str, session_id: str = None):
        """初始化Claude会话

        Args:
            cli_path: Claude CLI可执行文件路径
            working_dir: 工作目录
            session_id: Claude会话ID（可选）
        """
        self.cli_path = cli_path
        self.working_dir = working_dir
        self.session_id = session_id
        self._ready = False

    def _generate_session_id(self) -> str:
        """生成新的会话ID"""
        import uuid
        return f"feishu_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    def _ready_check(self):
        """检查会话是否就绪"""
        self._ready = True

    def send_message(self, message: str, timeout: int = 120) -> Optional[str]:
        """发送消息到Claude并获取响应

        Args:
            message: 要发送的消息
            timeout: 超时时间（秒）

        Returns:
            Claude的响应，失败返回None
        """
        try:
            # 构建 --print 模式命令
            cmd = [self.cli_path, "--print", message]

            print(f"[ClaudeSession] 执行命令: {' '.join(cmd)}")

            # 执行命令
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=os.environ.copy()
            )

            # 检查结果
            if result.returncode == 0 and result.stdout:
                response = result.stdout.strip()
                print(f"[ClaudeSession] 收到响应: {len(response)} 字符")
                return response
            elif result.stderr:
                # 如果有stderr，可能是Claude的输出
                response = result.stderr.strip()
                print(f"[ClaudeSession] 收到stderr: {len(response)} 字符")
                return response
            else:
                print(f"[ClaudeSession] 无输出，退出码: {result.returncode}")
                return None

        except subprocess.TimeoutExpired:
            print(f"[ClaudeSession] 执行超时")
            return None
        except Exception as e:
            print(f"[ClaudeSession] 执行失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def switch_session(self, session_id: str) -> bool:
        """切换到指定的Claude会话"""
        # --print 模式下，会话管理通过命令参数实现
        # 这里暂时返回False，表示不支持
        return False

    def list_sessions(self) -> List[dict]:
        """列出所有可用的Claude会话"""
        # --print 模式下不支持
        return []

    def new_session(self) -> bool:
        """创建新的Claude会话"""
        # --print 模式下不需要创建会话
        return True

    def close(self):
        """关闭Claude会话"""
        print(f"[ClaudeSession] 会话已关闭")

    def is_alive(self) -> bool:
        """检查会话是否存活"""
        return True
