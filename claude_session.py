#!/usr/bin/env python3
"""
Claude CLI 交互式会话管理

维护与Claude CLI的持久连接，支持发送消息、切换会话等操作
"""

import os
import subprocess
import threading
import queue
import time
import re
from typing import Optional, List


class ClaudeSession:
    """Claude CLI 交互式会话

    维护一个持久的Claude CLI进程，支持多轮对话
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
        self.process = None
        self._output_queue = queue.Queue()
        self._output_thread = None
        self._ready = False

        self._start_process()

    def _generate_session_id(self) -> str:
        """生成新的会话ID"""
        import uuid
        return f"feishu_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    def _start_process(self):
        """启动交互式Claude CLI进程"""
        cmd = [self.cli_path]

        # 如果指定了会话ID，使用该会话
        if self.session_id:
            cmd.extend(["--session", self.session_id])

        print(f"[ClaudeSession] 启动进程: {' '.join(cmd)}")
        print(f"[ClaudeSession] 工作目录: {self.working_dir}")

        self.process = subprocess.Popen(
            cmd,
            cwd=self.working_dir,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=os.environ.copy()
        )

        # 启动输出读取线程
        self._output_thread = threading.Thread(
            target=self._read_output,
            daemon=True
        )
        self._output_thread.start()

        # 等待进程就绪
        time.sleep(0.5)
        self._ready = True

        print(f"[ClaudeSession] 进程已启动 (PID: {self.process.pid})")

    def _read_output(self):
        """持续读取进程输出（后台线程）"""
        try:
            while self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    self._output_queue.put(line.rstrip())
                elif self.process.poll() is not None:
                    break
        except Exception as e:
            print(f"[ClaudeSession] 读取输出异常: {e}")

    def _is_response_complete(self, lines: List[str]) -> bool:
        """判断响应是否完成

        Claude CLI的响应结束标志：
        1. 检测到新的提示符（通常以 > 或类似符号开头）
        2. 空行后跟提示符
        """
        if len(lines) < 2:
            return False

        # 检查最后几行是否有提示符模式
        for line in lines[-3:]:
            # Claude CLI提示符通常包含 >
            if line.strip().startswith(">"):
                return True

        return False

    def _wait_for_response(self, timeout: int = 120) -> Optional[str]:
        """等待并获取完整响应

        Args:
            timeout: 超时时间（秒）

        Returns:
            完整响应文本，失败返回None
        """
        start_time = time.time()
        response_lines = []
        last_activity = time.time()
        idle_timeout = 3.0  # 3秒无输出认为响应结束

        while time.time() - start_time < timeout:
            try:
                # 尝试从队列获取输出（非阻塞）
                try:
                    line = self._output_queue.get(timeout=0.1)
                    response_lines.append(line)
                    last_activity = time.time()
                except queue.Empty:
                    pass

                # 检查是否超时无新输出
                if response_lines and self._is_response_complete(response_lines):
                    break

                if response_lines and (time.time() - last_activity) > idle_timeout:
                    break

                # 检查进程是否已结束
                if self.process.poll() is not None:
                    break

            except KeyboardInterrupt:
                break

        if response_lines:
            return "\n".join(response_lines)
        return None

    def send_message(self, message: str, timeout: int = 120) -> Optional[str]:
        """发送消息到Claude并等待响应

        Args:
            message: 要发送的消息
            timeout: 超时时间（秒）

        Returns:
            Claude的响应，失败返回None
        """
        if not self._ready or not self.process:
            print("[ClaudeSession] 会话未就绪")
            return None

        if self.process.poll() is not None:
            print("[ClaudeSession] 进程已终止")
            return None

        try:
            # 清空输出队列中残留的内容
            while not self._output_queue.empty():
                try:
                    self._output_queue.get_nowait()
                except queue.Empty:
                    break

            # 发送消息
            print(f"[ClaudeSession] 发送消息: {message[:50]}...")
            self.process.stdin.write(message + "\n")
            self.process.stdin.flush()

            # 等待响应
            response = self._wait_for_response(timeout)
            if response:
                print(f"[ClaudeSession] 收到响应: {len(response)} 字符")
                return response
            else:
                print("[ClaudeSession] 响应超时")
                return None

        except Exception as e:
            print(f"[ClaudeSession] 发送消息失败: {e}")
            return None

    def switch_session(self, session_id: str) -> bool:
        """切换到指定的Claude会话

        Args:
            session_id: 目标会话ID

        Returns:
            成功返回True，失败返回False
        """
        response = self.send_message(f"/switch {session_id}", timeout=30)
        if response and "Switched to" in response:
            self.session_id = session_id
            print(f"[ClaudeSession] 已切换到会话: {session_id}")
            return True
        print(f"[ClaudeSession] 切换会话失败: {response}")
        return False

    def list_sessions(self) -> List[dict]:
        """列出所有可用的Claude会话

        Returns:
            会话列表，每个会话包含 id 和 name 字段
        """
        response = self.send_message("/sessions", timeout=30)
        if not response:
            return []

        sessions = []
        # 解析 /sessions 命令的输出
        # 格式通常为: "1. Session Name [id]"
        for line in response.split("\n"):
            match = re.match(r"\s*\d+\.\s+(.+?)\s+\[([^\]]+)\]", line)
            if match:
                name, session_id = match.groups()
                sessions.append({
                    "name": name.strip(),
                    "id": session_id.strip()
                })

        print(f"[ClaudeSession] 找到 {len(sessions)} 个会话")
        return sessions

    def new_session(self) -> bool:
        """创建新的Claude会话

        Returns:
            成功返回True，失败返回False
        """
        response = self.send_message("/new", timeout=30)
        if response:
            # 生成新的会话ID
            self.session_id = self._generate_session_id()
            print(f"[ClaudeSession] 已创建新会话: {self.session_id}")
            return True
        return False

    def close(self):
        """关闭Claude会话"""
        if not self.process:
            return

        print(f"[ClaudeSession] 关闭会话...")

        try:
            # 发送退出命令
            self.process.stdin.write("/exit\n")
            self.process.stdin.flush()

            # 等待进程结束（最多5秒）
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # 超时则强制终止
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()

            print(f"[ClaudeSession] 会话已关闭")

        except Exception as e:
            print(f"[ClaudeSession] 关闭会话失败: {e}")

        finally:
            self.process = None
            self._ready = False

    def is_alive(self) -> bool:
        """检查会话是否存活

        Returns:
            进程运行中返回True，否则返回False
        """
        return self._ready and self.process and self.process.poll() is None

    def __del__(self):
        """析构函数，确保进程被清理"""
        self.close()
