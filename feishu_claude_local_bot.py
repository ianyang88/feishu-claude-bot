#!/usr/bin/env python3
"""
飞书-Claude本地CLI自动化Bot服务
监听飞书消息 → 自动调用本地Claude CLI → 自动回复飞书
"""

import json
import time
import os
import subprocess
import random
import fcntl
from pathlib import Path
from typing import Optional, List, Dict
from enum import Enum
from dataclasses import dataclass
import lark_oapi as lark
from project_manager import ProjectManager
from lark_oapi.api.im.v1 import (
    CreateMessageRequest, CreateMessageRequestBody,
    CreateMessageReactionRequest, CreateMessageReactionRequestBody
)
import requests

# ==================== 配置 ====================
FEISHU_APP_ID = "cli_a9103ecc9fb85bd8"
FEISHU_APP_SECRET = "qRyCROVPjtZDjCuZqDNIPdeWteHOnVck"
ENCRYPT_KEY = ""
VERIFICATION_TOKEN = ""

# Claude CLI配置
CLAUDE_CLI_PATH = "/home/ian/.npm-global/bin/claude"  # Claude CLI路径
WORKING_DIR = os.path.expanduser("~/projects")  # 工作目录 - Claude项目根目录

# 消息文件路径
MESSAGE_FILE = "/tmp/feishu_messages.jsonl"
PROCESSED_FILE = "/tmp/feishu_processed.jsonl"

# ==================== 授权机制数据结构 ====================

class PermissionLevel(Enum):
    """权限级别定义"""
    ADMIN = "admin"           # 管理员 - 所有权限
    TRUSTED = "trusted"       # 受信任用户 - 大部分操作
    STANDARD = "standard"     # 标准用户 - 基础操作
    RESTRICTED = "restricted" # 受限用户 - 只读操作

class OperationType(Enum):
    """操作类型及风险级别"""
    SAFE = "safe"                    # 安全操作 - 无需授权
    SENSITIVE_READ = "sensitive_read"  # 敏感读取 - 需要授权
    MODERATE = "moderate"            # 中等风险 - 需要授权
    DANGEROUS = "dangerous"          # 危险操作 - 需要授权
    CRITICAL = "critical"            # 关键操作 - 需要授权

@dataclass
class CommandPermission:
    """命令权限配置"""
    command: str
    operation_type: OperationType
    min_permission: PermissionLevel
    description: str
    examples: List[str]

# 命令权限映射表
COMMAND_PERMISSIONS = {
    "cd": CommandPermission(
        command="cd",
        operation_type=OperationType.SAFE,
        min_permission=PermissionLevel.STANDARD,
        description="切换工作目录",
        examples=["cd ~/projects", "cd .."]
    ),
    "pwd": CommandPermission(
        command="pwd",
        operation_type=OperationType.SAFE,
        min_permission=PermissionLevel.RESTRICTED,
        description="显示当前工作目录",
        examples=["pwd"]
    ),
    "ls": CommandPermission(
        command="ls",
        operation_type=OperationType.SENSITIVE_READ,
        min_permission=PermissionLevel.RESTRICTED,
        description="列出目录内容",
        examples=["ls", "ls /tmp"]
    ),
    "mkdir": CommandPermission(
        command="mkdir",
        operation_type=OperationType.MODERATE,
        min_permission=PermissionLevel.STANDARD,
        description="创建新目录",
        examples=["mkdir new-project"]
    ),
    "help": CommandPermission(
        command="help",
        operation_type=OperationType.SAFE,
        min_permission=PermissionLevel.RESTRICTED,
        description="显示帮助信息",
        examples=["help"]
    ),
    # 项目管理命令
    "projects": CommandPermission(
        command="projects",
        operation_type=OperationType.SENSITIVE_READ,
        min_permission=PermissionLevel.RESTRICTED,
        description="列出所有项目",
        examples=["projects", "proj"]
    ),
    "use": CommandPermission(
        command="use",
        operation_type=OperationType.SAFE,
        min_permission=PermissionLevel.RESTRICTED,
        description="切换到指定项目",
        examples=["use openclaw", "use fcb"]
    ),
    "search": CommandPermission(
        command="search",
        operation_type=OperationType.SENSITIVE_READ,
        min_permission=PermissionLevel.RESTRICTED,
        description="搜索项目",
        examples=["search bot", "search claude"]
    ),
    "addproj": CommandPermission(
        command="addproj",
        operation_type=OperationType.MODERATE,
        min_permission=PermissionLevel.STANDARD,
        description="添加新项目",
        examples=["addproj myapp ~/projects/my-app"]
    ),
    "delproj": CommandPermission(
        command="delproj",
        operation_type=OperationType.MODERATE,
        min_permission=PermissionLevel.STANDARD,
        description="删除项目",
        examples=["delproj myapp"]
    ),
    "clear": CommandPermission(
        command="clear",
        operation_type=OperationType.SAFE,
        min_permission=PermissionLevel.STANDARD,
        description="清理未处理消息和历史记录",
        examples=["clear", "reset"]
    ),
}

# ==================== Reaction选择器 ====================

class UserPermissionConfig:
    """用户权限管理"""

    DEFAULT_PERMISSION = PermissionLevel.RESTRICTED

    # 用户权限映射 (sender_id -> PermissionLevel)
    USER_PERMISSIONS = {
        # 管理员示例（替换为实际用户ID）
        "ou_1cff6f93d95c060d09bc55f4b6d8ff5f": PermissionLevel.ADMIN,
    }

    @classmethod
    def get_user_permission(cls, sender_id: str) -> PermissionLevel:
        """获取用户权限级别"""
        return cls.USER_PERMISSIONS.get(sender_id, cls.DEFAULT_PERMISSION)

    @classmethod
    def set_user_permission(cls, sender_id: str, level: PermissionLevel):
        """设置用户权限级别"""
        cls.USER_PERMISSIONS[sender_id] = level

    @classmethod
    def can_execute_command(cls, sender_id: str, command: str) -> tuple[bool, str]:
        """
        检查用户是否可以执行命令

        Returns:
            (can_execute, reason)
        """
        user_perm = cls.get_user_permission(sender_id)

        if command not in COMMAND_PERMISSIONS:
            return False, f"未知命令: {command}"

        cmd_perm = COMMAND_PERMISSIONS[command]
        min_perm = cmd_perm.min_permission

        perm_order = {
            PermissionLevel.RESTRICTED: 0,
            PermissionLevel.STANDARD: 1,
            PermissionLevel.TRUSTED: 2,
            PermissionLevel.ADMIN: 3,
        }

        if perm_order[user_perm] >= perm_order[min_perm]:
            return True, "权限满足"

        return False, f"权限不足 (需要: {min_perm.value}, 当前: {user_perm.value})"

@dataclass
class AuthRequest:
    """授权请求"""
    request_id: str
    sender_id: str
    chat_id: str
    command: str
    args: str
    operation_type: OperationType
    created_at: float
    expires_at: float
    status: str = "pending"

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

class AuthRequestManager:
    """授权请求管理器"""

    def __init__(self):
        self.pending_requests: Dict[str, AuthRequest] = {}
        self.request_timeout = 300  # 5分钟

    def create_request(self, sender_id: str, chat_id: str,
                      command: str, args: str,
                      operation_type: OperationType) -> AuthRequest:
        """创建新的授权请求"""
        request_id = f"auth_{int(time.time() * 1000)}_{sender_id[:8]}"

        timeout = self.request_timeout
        if operation_type == OperationType.CRITICAL:
            timeout = 120
        elif operation_type == OperationType.DANGEROUS:
            timeout = 180

        request = AuthRequest(
            request_id=request_id,
            sender_id=sender_id,
            chat_id=chat_id,
            command=command,
            args=args,
            operation_type=operation_type,
            created_at=time.time(),
            expires_at=time.time() + timeout
        )

        self.pending_requests[request_id] = request
        return request

    def get_request(self, request_id: str) -> Optional[AuthRequest]:
        return self.pending_requests.get(request_id)

    def approve_request(self, request_id: str) -> bool:
        request = self.get_request(request_id)
        if request and not request.is_expired():
            request.status = "approved"
            del self.pending_requests[request_id]
            return True
        return False

    def reject_request(self, request_id: str) -> bool:
        request = self.get_request(request_id)
        if request:
            request.status = "rejected"
            del self.pending_requests[request_id]
            return True
        return False

class AuditLogger:
    """操作审计日志记录器"""

    def __init__(self, log_file: str = "/tmp/feishu_audit.jsonl"):
        self.log_file = log_file

    def log_operation(self, sender_id: str, chat_id: str, command: str,
                     args: str, operation_type: OperationType,
                     status: str, result: str = "", metadata: dict = None):
        """记录操作日志"""
        log_entry = {
            "timestamp": int(time.time() * 1000),
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sender_id": sender_id,
            "chat_id": chat_id,
            "command": command,
            "args": args,
            "operation_type": operation_type.value,
            "status": status,
            "result": result[:200] if result else "",
            "metadata": metadata or {}
        }

        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[错误] 写入审计日志失败: {str(e)}")

class AuthorizationManager:
    """授权管理器 - 整合所有授权相关功能"""

    def __init__(self, audit_logger: AuditLogger = None):
        self.auth_requests = AuthRequestManager()
        self.audit_logger = audit_logger or AuditLogger()

    def check_permission(self, sender_id: str, command: str) -> tuple[bool, str, OperationType]:
        """
        检查用户权限

        Returns:
            (has_permission, reason, operation_type)
        """
        if command not in COMMAND_PERMISSIONS:
            return False, f"未知命令: {command}", OperationType.SAFE

        cmd_perm = COMMAND_PERMISSIONS[command]
        can_execute, reason = UserPermissionConfig.can_execute_command(
            sender_id, command
        )

        return can_execute, reason, cmd_perm.operation_type

    def requires_authorization(self, operation_type: OperationType) -> bool:
        """判断操作类型是否需要授权"""
        return operation_type in [
            OperationType.SENSITIVE_READ,
            OperationType.MODERATE,
            OperationType.DANGEROUS,
            OperationType.CRITICAL
        ]

    def create_auth_request(self, sender_id: str, chat_id: str,
                           command: str, args: str,
                           operation_type: OperationType) -> AuthRequest:
        """创建授权请求"""
        request = self.auth_requests.create_request(
            sender_id, chat_id, command, args, operation_type
        )
        self.audit_logger.log_operation(
            sender_id, chat_id, command, args, operation_type,
            "auth_pending", metadata={"request_id": request.request_id}
        )
        return request

    def process_command(self, sender_id: str, chat_id: str,
                       command: str, args: str) -> tuple[bool, str, Optional[AuthRequest]]:
        """
        处理命令授权检查

        Returns:
            (can_execute, message, auth_request)
        """
        has_perm, reason, op_type = self.check_permission(sender_id, command)

        if not has_perm:
            self.audit_logger.log_operation(
                sender_id, chat_id, command, args, op_type,
                "denied", reason
            )
            return False, f"❌ {reason}", None

        if not self.requires_authorization(op_type):
            return True, "权限验证通过", None

        auth_req = self.create_auth_request(
            sender_id, chat_id, command, args, op_type
        )

        confirm_msg = self._generate_auth_request_message(auth_req)
        return False, confirm_msg, auth_req

    def handle_confirmation(self, sender_id: str, message: str, chat_id: str) -> tuple[bool, str, Optional[AuthRequest]]:
        """
        处理用户确认消息

        支持两种格式:
        1. 简单格式: "确认"/"取消" - 针对最新待处理请求
        2. 完整格式: "confirm <request_id>" / "reject <request_id>"

        Returns:
            (approved, message, auth_request)
        """
        message = message.strip()

        # 简单格式: 确认/取消 (针对最新待处理请求)
        if message in ['确认', '取消', 'confirm', 'cancel', 'yes', 'no', 'y', 'n']:
            # 获取该用户最新的待处理请求
            latest_request = None
            for req_id, req in self.auth_requests.pending_requests.items():
                if req.sender_id == sender_id and req.status == "pending":
                    if not latest_request or req.created_at > latest_request.created_at:
                        latest_request = req

            if not latest_request:
                return False, "❌ 没有待处理的授权请求", None

            # 判断操作类型
            is_approve = message in ['确认', 'confirm', 'yes', 'y']
            request_id = latest_request.request_id

            if is_approve:
                success = self.auth_requests.approve_request(request_id)
                if success:
                    self.audit_logger.log_operation(
                        sender_id, chat_id=latest_request.chat_id,
                        command=latest_request.command, args=latest_request.args,
                        operation_type=latest_request.operation_type,
                        status="auth_approved",
                        metadata={"request_id": latest_request.request_id}
                    )
                    return True, f"✅ 授权已批准，执行命令: {latest_request.command}", latest_request
                else:
                    return False, "❌ 授权请求已过期", None
            else:
                self.auth_requests.reject_request(request_id)
                self.audit_logger.log_operation(
                    sender_id, chat_id=latest_request.chat_id,
                    command=latest_request.command, args=latest_request.args,
                    operation_type=latest_request.operation_type,
                    status="auth_rejected",
                    metadata={"request_id": latest_request.request_id}
                )
                return False, "❌ 授权已拒绝", latest_request

        # 完整格式: confirm/reject <request_id>
        parts = message.split()
        if len(parts) < 2:
            return False, "❌ 无效格式，回复'确认'批准或'取消'拒绝", None

        action = parts[0].lower()
        request_id = parts[1]

        request = self.auth_requests.get_request(request_id)
        if not request:
            return False, f"❌ 授权请求不存在或已过期: {request_id}", None

        if request.sender_id != sender_id:
            return False, "❌ 无权确认此授权请求", None

        if action == "confirm":
            success = self.auth_requests.approve_request(request_id)
            if success:
                self.audit_logger.log_operation(
                    sender_id, chat_id=request.chat_id,
                    command=request.command, args=request.args,
                    operation_type=request.operation_type,
                    status="auth_approved",
                    metadata={"request_id": request.request_id}
                )
                return True, f"✅ 授权已批准，执行命令: {request.command}", request
            else:
                return False, "❌ 授权请求已过期", None

        elif action == "reject":
            self.auth_requests.reject_request(request_id)
            self.audit_logger.log_operation(
                sender_id, chat_id=request.chat_id,
                command=request.command, args=request.args,
                operation_type=request.operation_type,
                status="auth_rejected",
                metadata={"request_id": request.request_id}
            )
            return False, "❌ 授权已拒绝", request

        else:
            return False, f"❌ 未知操作: {action}，回复'确认'批准或'取消'拒绝", None

    def _generate_auth_request_message(self, request: AuthRequest) -> str:
        """生成授权请求消息"""
        operation_desc = {
            OperationType.SENSITIVE_READ: "📖 敏感信息读取",
            OperationType.MODERATE: "⚠️ 中等风险操作",
            OperationType.DANGEROUS: "🔥 危险操作",
            OperationType.CRITICAL: "💥 关键操作",
        }.get(request.operation_type, "🔒 需要授权")

        timeout_sec = int(request.expires_at - time.time())

        return f"""{operation_desc}

命令: {request.command} {request.args}
操作类型: {request.operation_type.value}
超时时间: {timeout_sec} 秒

⚠️ 此操作需要您的授权确认

💬 回复「确认」批准，「取消」拒绝

或使用完整格式:
  confirm {request.request_id}  - 执行操作
  reject {request.request_id}   - 取消操作"""

class ReactionSelector:
    """Reaction选择策略 - 根据消息内容智能选择emoji"""

    # 飞书预定义的emoji_type常量
    # 参考: https://open.feishu.cn/document/server-docs/im-v1/message-reaction/emojis-introduce
    FEISHU_EMOJI_TYPES = {
        "THUMBSUP": "👍",
        "THUMBSDOWN": "👎",
        "HEART": "❤️",
        "SMILE": "😊",
        "GRINNING": "😀",
        "LAUGHING": "😆",
        "CRY": "😢",
        "ANGRY": "😡",
        "SURPRISED": "😮",
        "THINKING": "🤔",
        "CLAP": "👏",
        "OK": "👌",
        "FIST": "✊",
        "PRAY": "🙏",
        "FIRE": "🔥",
        "PARTY": "🎉",
        "CHECK": "✅",
        "CROSS": "❌",
        "QUESTION": "❓",
        "EXCLAMATION": "❗",
    }

    # 语境-emoji映射（使用飞书emoji_type常量）
    CONTEXT_EMOJIS = {
        "greeting": ["WAVE", "SMILE", "PARTY"],  # WAVE可能不在预定义中
        "thanks": ["HEART", "PRAY", "SMILE"],
        "question": ["THINKING", "QUESTION", "OK"],
        "praise": ["THUMBSUP", "PARTY", "FIRE", "CLAP"],
        "success": ["PARTY", "GRINNING", "FIST", "CHECK"],
        "error": ["CRY", "ANGRY", "CROSS"],
        "technical": ["OK", "THINKING", "FIRE"],
        "default": ["SMILE", "THUMBSUP", "HEART", "OK"]
    }

    CONTEXT_KEYWORDS = {
        "greeting": ["你好", "嗨", "hi", "hello", "早上好", "晚上好"],
        "thanks": ["谢谢", "感谢", "thank", "thanks"],
        "question": ["?", "？", "怎么", "如何", "什么", "为什么"],
        "praise": ["厉害", "棒", "good", "great", "赞"],
        "success": ["成功", "完成", "done", "搞定"],
        "error": ["错误", "error", "失败", "fail", "bug"],
        "technical": ["代码", "程序", "api", "function", "算法"]
    }

    @classmethod
    def select_emoji_type(cls, message_text: str) -> str:
        """根据消息内容选择合适的飞书emoji_type常量"""
        if not message_text:
            return cls._random_emoji("default")

        message_lower = message_text.lower()

        for context, keywords in cls.CONTEXT_KEYWORDS.items():
            if any(keyword in message_lower for keyword in keywords):
                return cls._random_emoji(context)

        return cls._random_emoji("default")

    @classmethod
    def _random_emoji(cls, context: str) -> str:
        emoji_types = cls.CONTEXT_EMOJIS.get(context, cls.CONTEXT_EMOJIS["default"])
        return random.choice(emoji_types)

# ==================== Claude CLI客户端 ====================

class ClaudeCLIClient:
    """Claude CLI客户端 - 使用本地Claude CLI"""

    def __init__(self, cli_path: str, working_dir: str):
        self.cli_path = cli_path
        self.working_dir = working_dir

    def chat(self, message: str, conversation_history: List[dict] = None, timeout: int = 120) -> Optional[str]:
        """调用Claude CLI处理消息"""

        try:
            # 构建完整提示（包含历史对话上下文）
            full_prompt = self._build_prompt(message, conversation_history)

            # 调用Claude CLI（使用--print模式获取非交互式输出，跳过权限检查）
            cmd = [
                self.cli_path,
                "--print",
                "--dangerously-skip-permissions",
                full_prompt
            ]

            print(f"[🤖] 调用Claude CLI...")
            print(f"[📝] 输入: {message[:100]}..." if len(message) > 100 else f"[📝] 输入: {message}")

            # 执行命令
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,  # 可配置超时时间
                env=os.environ.copy()
            )

            if result.returncode == 0:
                response = result.stdout.strip()
                print(f"[✅] Claude回复: {response[:100]}..." if len(response) > 100 else f"[✅] Claude回复: {response}")
                return response
            else:
                # 如果有stderr输出，说明Claude CLI正常执行了，只是返回了错误
                # 这种情况下应该把错误信息返回给用户，而不是当作"调用失败"
                if result.stderr and result.stderr.strip():
                    print(f"[ℹ️] Claude CLI返回错误（退出码: {result.returncode}）")
                    print(f"[stderr] {result.stderr}")
                    # 将stderr作为正常返回值，让用户看到实际的错误信息
                    return result.stderr
                else:
                    # 没有stderr但退出码非0，这才是真正的调用失败
                    print(f"[❌] Claude CLI调用失败（退出码: {result.returncode}，无错误输出）")
                    return None

        except subprocess.TimeoutExpired:
            print(f"[❌] Claude CLI执行超时")
            return None
        except Exception as e:
            print(f"[❌] 调用Claude CLI异常: {str(e)}")
            return None

    def chat_streaming(self, message: str, on_chunk: callable, conversation_history: List[dict] = None, timeout: int = 120) -> Optional[str]:
        """流式调用Claude CLI，每行输出都触发on_chunk回调

        Args:
            message: 用户消息
            on_chunk: 回调函数，接收累积的输出内容
            conversation_history: 对话历史
            timeout: 超时时间（秒）

        Returns:
            str: 完整的Claude回复，失败返回None
        """
        import select

        try:
            # 构建完整提示
            full_prompt = self._build_prompt(message, conversation_history)

            # 调用Claude CLI
            cmd = [
                self.cli_path,
                "--print",
                "--dangerously-skip-permissions",
                full_prompt
            ]

            print(f"[🤖] 调用Claude CLI（流式模式）...")
            print(f"[📝] 输入: {message[:100]}..." if len(message) > 100 else f"[📝] 输入: {message}")

            # 使用Popen实现流式读取
            process = subprocess.Popen(
                cmd,
                cwd=self.working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # 行缓冲
                env=os.environ.copy()
            )

            accumulated = []
            stderr_buffer = []  # 收集stderr输出，防止buffer deadlock
            last_chunk_time = time.time()
            line_read_timeout = timeout  # 使用与外部相同的超时时间，避免提前判定挂起

            try:
                # 使用select实现带超时的行读取，避免无限期阻塞
                stdout_complete = False
                last_output_time = time.time()

                while True:
                    # 先检查进程是否已结束
                    if process.poll() is not None:
                        # 进程已结束，读取所有剩余输出
                        remaining = process.stdout.read() if not process.stdout.closed else ''
                        if remaining:
                            for line in remaining.splitlines():
                                line = line.rstrip('\n\r')
                                if line:
                                    accumulated.append(line)
                        break

                    # 使用select检查stdout和stderr是否有数据可读
                    readable, _, _ = select.select([process.stdout, process.stderr], [], [], 1.0)  # 1秒超时

                    if readable:
                        # 有数据可读，更新最后输出时间
                        last_output_time = time.time()

                        for stream in readable:
                            if stream == process.stdout:
                                line = process.stdout.readline()
                                if line:  # 有数据
                                    stripped_line = line.rstrip('\n\r')
                                    accumulated.append(stripped_line)
                                    current_content = '\n'.join(accumulated)

                                    # 触发回调（至少每0.1秒一次）
                                    now = time.time()
                                    if now - last_chunk_time >= 0.1:
                                        on_chunk(current_content)
                                        last_chunk_time = now
                                else:
                                    # EOF，stdout 读取完成
                                    print(f"[调试] 检测到 EOF，读取剩余输出")
                                    # 读取所有剩余输出
                                    remaining = process.stdout.read() if not process.stdout.closed else ''
                                    if remaining:
                                        for l in remaining.splitlines():
                                            l = l.rstrip('\n\r')
                                            if l:
                                                accumulated.append(l)
                                    stdout_complete = True
                                    break  # 退出 for 循环
                            elif stream == process.stderr:
                                # 消费stderr防止buffer deadlock
                                err_line = process.stderr.readline()
                                if err_line:
                                    stderr_buffer.append(err_line)
                                    print(f"[stderr] {err_line.strip()}")

                        # 如果 stdout 已完成，退出主循环
                        if stdout_complete:
                            break
                    else:
                        # 没有数据可读
                        # 检查是否长时间无输出（可能进程挂起）
                        if time.time() - last_output_time > line_read_timeout:
                            print(f"[警告] 进程无输出超时（{line_read_timeout}秒），检查进程状态")
                            if process.poll() is not None:
                                # 进程已结束，正常退出
                                break
                            else:
                                # 进程还在运行但无输出，可能挂起
                                print(f"[错误] 进程挂起，终止进程")
                                process.kill()
                                process.wait()
                                return None

                # 确保所有剩余输出都被读取
                if not stdout_complete:
                    # 读取stdout的剩余内容
                    try:
                        remaining_output = process.stdout.read() if not process.stdout.closed else ''
                        if remaining_output:
                            for line in remaining_output.splitlines():
                                line = line.rstrip('\n\r')
                                if line:
                                    accumulated.append(line)
                    except:
                        pass

                # 最终回调
                final_content = '\n'.join(accumulated)
                if final_content:
                    on_chunk(final_content)

                # 确保进程已被回收
                if process.poll() is None:
                    process.wait(timeout=5)

                if process.returncode == 0:
                    print(f"[✅] Claude回复（流式）: {final_content[:100]}..." if len(final_content) > 100 else f"[✅] Claude回复（流式）: {final_content}")
                    print(f"[调试] 完整内容长度: {len(final_content)} 字符, 行数: {len(accumulated)}")
                    return final_content
                else:
                    # 使用已收集的stderr buffer，并尝试读取剩余内容
                    remaining_stderr = process.stderr.read() if not process.stderr.closed else ''
                    stderr_output = ''.join(stderr_buffer) + remaining_stderr

                    # 如果有stderr输出，说明Claude CLI正常执行了，只是返回了错误
                    # 这种情况下应该把错误信息返回给用户，而不是当作"调用失败"
                    if stderr_output.strip():
                        print(f"[ℹ️] Claude CLI返回错误（退出码: {process.returncode}）")
                        print(f"[stderr] {stderr_output}")
                        # 将stderr作为正常返回值，让用户看到实际的错误信息
                        return stderr_output
                    else:
                        # 没有stderr但退出码非0，这才是真正的调用失败
                        print(f"[❌] Claude CLI调用失败（退出码: {process.returncode}，无错误输出）")
                        return None

            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                print(f"[❌] Claude CLI执行超时")
                return None

        except Exception as e:
            print(f"[❌] 调用Claude CLI异常: {str(e)}")
            return None

    def set_working_dir(self, working_dir: str) -> bool:
        """动态设置工作目录"""
        if os.path.isdir(working_dir):
            self.working_dir = working_dir
            return True
        return False

    def get_working_dir(self) -> str:
        """获取当前工作目录"""
        return self.working_dir

    def _build_prompt(self, message: str, conversation_history: List[dict] = None) -> str:
        """构建完整的提示词（包含对话历史）"""

        prompt_parts = []

        # 添加系统提示
        prompt_parts.append("""你是一个AI助手，名为Claude，运行在Ian的电脑上。
你通过本地Claude CLI与飞书机器人集成，为用户提供服务。

你的身份特点：
- 你是Ian电脑上的Claude CLI
- 你通过本地终端运行，不是云服务
- 你可以帮助用户完成各种任务，包括编程、写作、分析等

如果是首次对话，请主动介绍自己，例如：
"你好！我是Ian电脑上的Claude CLI，很高兴为你服务！"
""")

        # 添加对话历史
        if conversation_history and len(conversation_history) > 0:
            prompt_parts.append("=== 之前的对话 ===")
            for msg in conversation_history[-6:]:  # 只保留最近6条历史
                role = "用户" if msg["role"] == "user" else "助手"
                prompt_parts.append(f"{role}: {msg['content']}")
            prompt_parts.append("\n")

        # 添加当前消息
        prompt_parts.append("=== 当前消息 ===")
        prompt_parts.append(message)

        return "\n".join(prompt_parts)


# ==================== 飞书客户端 ====================

class ThrottledUpdater:
    """节流更新器，避免频繁调用 API"""

    def __init__(self, update_func: callable, interval: float = 0.5):
        self.update_func = update_func
        self.interval = interval
        self.last_update = 0

    def update(self, content: str):
        """节流更新，只有超过间隔时间才会真正执行"""
        now = time.time()
        if now - self.last_update >= self.interval:
            self._safe_update(content)
            self.last_update = now

    def force_update(self, content: str):
        """强制更新，无视节流间隔（用于最终结果）"""
        self._safe_update(content)
        self.last_update = time.time()

    def _safe_update(self, content: str):
        """安全执行更新，捕获异常避免阻塞"""
        try:
            self.update_func(content)
        except Exception as e:
            print(f"[警告] 卡片更新失败: {str(e)}")
            # 不抛出异常，避免阻塞流式处理


class FeishuClient:
    """飞书客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_access_token = None
        self.token_expire_time = 0
        self._card_sequence = {}  # 卡片序号管理
        self._card_update_keys = {}  # 卡片更新键管理 (message_id -> update_key)

    def get_tenant_access_token(self) -> str:
        """获取tenant_access_token"""
        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()

            if data.get("code") == 0:
                return data.get("tenant_access_token")
            else:
                print(f"[错误] 获取tenant_access_token失败: {data}")
                return None
        except Exception as e:
            print(f"[错误] 获取token异常: {str(e)}")
            return None

    def send_message(self, chat_id: str, text: str) -> bool:
        """发送文本消息到飞书群聊"""
        token = self.get_tenant_access_token()
        if not token:
            return False

        try:
            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            content = json.dumps({"text": text})
            payload = {
                "receive_id": chat_id,
                "msg_type": "text",
                "content": content
            }

            response = requests.post(
                f"{url}?receive_id_type=chat_id",
                headers=headers,
                json=payload,
                timeout=10
            )

            data = response.json()
            if data.get("code") == 0:
                print(f"[✅] 回复已发送到飞书")
                return True
            else:
                print(f"[❌] 发送消息失败: {data}")
                return False

        except Exception as e:
            print(f"[错误] 发送消息异常: {str(e)}")
            return False

    def send_reaction(self, message_id: str, emoji_type: str) -> bool:
        """给消息添加reaction（使用飞书SDK）

        Args:
            message_id: 飞书消息ID
            emoji_type: 飞书emoji_type常量（如"THUMBSUP", "SMILE"等）

        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            # 创建飞书client
            client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .build()

            # 构建请求 - 使用正确的格式：reaction_type包含emoji_type字段
            # 参考: https://open.feishu.cn/document/server-docs/im-v1/message-reaction/create
            reaction_data = {
                "emoji_type": emoji_type
            }

            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(CreateMessageReactionRequestBody.builder()
                    .reaction_type(reaction_data)
                    .build()) \
                .build()

            # 发送请求
            response = client.im.v1.message_reaction.create(request)

            # 打印调试信息
            emoji_display = ReactionSelector.FEISHU_EMOJI_TYPES.get(emoji_type, emoji_type)
            print(f"[DEBUG] Reaction SDK call:")
            print(f"[DEBUG] Message ID: {message_id}")
            print(f"[DEBUG] Emoji type: {emoji_type} ({emoji_display})")
            print(f"[DEBUG] Response code: {response.code}")
            if response.msg:
                print(f"[DEBUG] Response msg: {response.msg}")

            if response.code == 0:
                print(f"[✅] Reaction已发送: {emoji_type} {emoji_display}")
                return True
            else:
                print(f"[❌] 发送reaction失败: code={response.code}, msg={response.msg}")
                return False

        except Exception as e:
            print(f"[错误] 发送reaction异常: {str(e)}")
            import traceback
            print(f"[TRACEBACK] {traceback.format_exc()}")
            return False

    def _get_next_sequence(self, message_id: str) -> int:
        """获取并递增卡片操作序号"""
        if message_id not in self._card_sequence:
            self._card_sequence[message_id] = 0
        self._card_sequence[message_id] += 1
        return self._card_sequence[message_id]

    def _build_card_content(self, title: str, content: str, update_key: str = None) -> dict:
        """构建飞书卡片内容

        Args:
            title: 卡片标题
            content: 卡片内容（Markdown格式）
            update_key: 更新键（用于支持多次更新）

        Returns:
            dict: 飞书卡片JSON结构
        """
        # 内容长度限制（飞书卡片内容最大约3000字符）
        max_content_length = 2800
        if len(content) > max_content_length:
            # 截断并添加提示
            content = content[:max_content_length] + "\n\n... (内容过长，已截断)"

        card = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "content": title,
                    "tag": "plain_text"
                }
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": content
                    }
                }
            ]
        }

        # 添加update_key以支持多次更新
        if update_key:
            card["update_key"] = update_key

        return card

    def create_and_send_card(self, chat_id: str, content: str, title: str = "🤖 Claude") -> Optional[str]:
        """创建并发送卡片消息到聊天，返回 message_id

        Args:
            chat_id: 聊天ID
            content: 卡片内容（Markdown格式）
            title: 卡片标题

        Returns:
            message_id: 成功返回消息ID，失败返回None
        """
        try:
            token = self.get_tenant_access_token()
            if not token:
                print("[错误] 获取tenant_access_token失败")
                return None

            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # 生成唯一的update_key（基于时间戳和随机数）
            import uuid
            update_key = f"card_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"

            # 构建卡片内容（包含update_key）
            card_data = self._build_card_content(title, content, update_key)

            payload = {
                "receive_id": chat_id,
                "msg_type": "interactive",
                "content": json.dumps(card_data, ensure_ascii=False)
            }

            response = requests.post(
                f"{url}?receive_id_type=chat_id",
                headers=headers,
                json=payload,
                timeout=10
            )

            data = response.json()
            if data.get("code") == 0:
                message_id = data.get("data", {}).get("message_id")
                # 保存update_key用于后续更新
                self._card_update_keys[message_id] = update_key
                print(f"[✅] 卡片消息已发送: {message_id} (update_key: {update_key})")
                return message_id
            else:
                print(f"[❌] 发送卡片消息失败: {data}")
                return None

        except Exception as e:
            print(f"[错误] 发送卡片消息异常: {str(e)}")
            return None

    def update_card_message(self, message_id: str, content: str, title: str = "🤖 Claude") -> bool:
        """更新卡片消息内容

        Args:
            message_id: 消息ID
            content: 新的卡片内容（Markdown格式）
            title: 卡片标题

        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            token = self.get_tenant_access_token()
            if not token:
                print("[错误] 获取tenant_access_token失败")
                return False

            # 获取之前保存的update_key
            update_key = self._card_update_keys.get(message_id)
            if not update_key:
                print(f"[警告] 未找到卡片 {message_id} 的update_key，可能无法多次更新")

            url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            # 构建卡片内容（包含update_key以支持多次更新）
            card_data = self._build_card_content(title, content, update_key)

            payload = {
                "msg_type": "interactive",
                "content": json.dumps(card_data, ensure_ascii=False)
            }

            response = requests.patch(url, headers=headers, json=payload, timeout=10)
            data = response.json()

            if data.get("code") == 0:
                # 序号递增（用于调试）
                sequence = self._get_next_sequence(message_id)
                print(f"[✅] 卡片更新成功 (序号: {sequence}, 内容长度: {len(content)})")
                return True
            else:
                print(f"[❌] 更新卡片失败: {data}")
                return False

        except Exception as e:
            print(f"[错误] 更新卡片异常: {str(e)}")
            return False

    def send_long_content(self, chat_id: str, content: str) -> int:
        """分段发送长内容，自动分割成多条消息

        Args:
            chat_id: 聊天ID
            content: 要发送的内容

        Returns:
            int: 成功发送的消息数量
        """
        # 飞书文本消息长度限制（约4000字符，安全值3000）
        max_length = 3000
        sent_count = 0

        if len(content) <= max_length:
            # 内容较短，直接发送
            if self.send_message(chat_id, content):
                return 1
            return 0

        # 内容过长，需要分割
        parts = []
        current_part = ""

        # 按段落分割（保留段落结构）
        paragraphs = content.split('\n\n')
        current_length = 0

        for para in paragraphs:
            para_length = len(para)

            if current_length + para_length + 2 <= max_length:
                # 可以加入当前部分
                if current_part:
                    current_part += "\n\n" + para
                else:
                    current_part = para
                current_length += para_length + 2
            else:
                # 当前部分已满，保存并开始新部分
                if current_part:
                    parts.append(current_part)
                current_part = para
                current_length = para_length

        # 添加最后的部分
        if current_part:
            parts.append(current_part)

        # 发送各部分
        for i, part in enumerate(parts):
            # 添加续接标记
            if i > 0:
                part = f"...（续）\n\n{part}"
            if i < len(parts) - 1:
                part = f"{part}\n\n...（未完待续）"

            if self.send_message(chat_id, part):
                sent_count += 1
                # 分段之间短暂延迟，避免触发限流
                if i < len(parts) - 1:
                    time.sleep(0.5)

        print(f"[分段] 内容已分成 {len(parts)} 部分发送，成功 {sent_count} 部")
        return sent_count


# ==================== 消息处理器 ====================

class MessageProcessor:
    """消息处理器 - 监听并自动回复"""

    def __init__(self):
        self.feishu = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
        self.claude = ClaudeCLIClient(CLAUDE_CLI_PATH, WORKING_DIR)
        self.processed_ids = set()
        self.conversation_history = {}  # 每个聊天ID的对话历史
        # 工作目录管理
        self.chat_working_dirs = {}  # chat_id -> working_dir 映射
        self.default_working_dir = WORKING_DIR
        self.processing_lock = None  # 处理锁文件

        # 初始化授权管理器
        self.auth_manager = AuthorizationManager(
            audit_logger=AuditLogger("/tmp/feishu_audit.jsonl")
        )

        # 初始化项目管理器
        self.project_manager = ProjectManager()

    def load_processed_ids(self):
        """加载已处理的消息ID"""
        if os.path.exists(PROCESSED_FILE):
            try:
                with open(PROCESSED_FILE, 'r') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            self.processed_ids.add(data['message_id'])
                print(f"[加载] 已处理消息ID: {len(self.processed_ids)} 条")
            except Exception as e:
                print(f"[警告] 加载已处理消息ID失败: {str(e)}")

    def save_processed_id(self, message_id: str):
        """保存已处理的消息ID（使用原子写入）"""
        try:
            # 使用原子写入避免文件损坏
            temp_file = PROCESSED_FILE + ".tmp"
            with open(temp_file, 'a') as f:
                f.write(json.dumps({"message_id": message_id}) + '\n')
                f.flush()
                os.fsync(f.fileno())

            # 重命名到目标文件（原子操作）
            os.rename(temp_file, PROCESSED_FILE)

            self.processed_ids.add(message_id)
        except Exception as e:
            print(f"[错误] 保存已处理消息ID失败: {str(e)}")

    def parse_content(self, content_str: str) -> str:
        """解析飞书消息内容"""
        try:
            content = json.loads(content_str)
            if 'text' in content:
                return content['text']
            else:
                return str(content)
        except:
            return content_str

    def get_conversation_history(self, chat_id: str) -> list:
        """获取对话历史"""
        if chat_id not in self.conversation_history:
            self.conversation_history[chat_id] = []
        return self.conversation_history[chat_id]

    def add_to_history(self, chat_id: str, role: str, content: str):
        """添加到对话历史"""
        if chat_id not in self.conversation_history:
            self.conversation_history[chat_id] = []

        self.conversation_history[chat_id].append({
            "role": role,
            "content": content
        })

        # 保持历史记录在合理范围内（最近20条）
        if len(self.conversation_history[chat_id]) > 20:
            self.conversation_history[chat_id] = self.conversation_history[chat_id][-20:]

    def get_working_dir(self, chat_id: str) -> str:
        """获取指定 chat_id 的工作目录"""
        return self.chat_working_dirs.get(chat_id, self.default_working_dir)

    def set_working_dir(self, chat_id: str, path: str) -> tuple[bool, str]:
        """
        设置指定 chat_id 的工作目录

        Returns:
            (success, message): (是否成功, 结果消息)
        """
        # 展开波浪号
        expanded_path = os.path.expanduser(path)

        # 转换为绝对路径
        if not os.path.isabs(expanded_path):
            current_dir = self.get_working_dir(chat_id)
            expanded_path = os.path.abspath(os.path.join(current_dir, expanded_path))

        # 验证目录存在
        if not os.path.isdir(expanded_path):
            return False, f"❌ 目录不存在：{expanded_path}"

        # 验证可访问权限
        if not os.access(expanded_path, os.R_OK | os.X_OK):
            return False, f"❌ 无权限访问目录：{expanded_path}"

        # 保存工作目录
        self.chat_working_dirs[chat_id] = expanded_path
        return True, f"✅ 工作目录已切换到：{expanded_path}"

    def parse_command(self, message: str) -> tuple[bool, str, str]:
        """
        解析消息是否为控制命令

        Returns:
            (is_command, command_type, args)
        """
        import re

        message = message.strip()

        # 项目管理命令
        if message in ['projects', 'proj', '项目']:
            return True, 'projects', ''

        use_match = re.match(r'^use\s+(.+)$', message)
        if use_match:
            return True, 'use', use_match.group(1).strip()

        addproj_match = re.match(r'^addproj\s+(.+)$', message)
        if addproj_match:
            return True, 'addproj', addproj_match.group(1).strip()

        delproj_match = re.match(r'^delproj\s+(.+)$', message)
        if delproj_match:
            return True, 'delproj', delproj_match.group(1).strip()

        search_match = re.match(r'^search\s+(.+)$', message)
        if search_match:
            return True, 'search', search_match.group(1).strip()

        # cd 命令
        cd_match = re.match(r'^cd\s+(.+)$', message)
        if cd_match:
            return True, 'cd', cd_match.group(1).strip()

        # pwd 命令
        if message == 'pwd':
            return True, 'pwd', ''

        # ls 命令
        ls_match = re.match(r'^ls(?:\s+(.*))?$', message)
        if ls_match:
            return True, 'ls', ls_match.group(1).strip() if ls_match.group(1) else ''

        # mkdir 命令
        mkdir_match = re.match(r'^mkdir\s+(.+)$', message)
        if mkdir_match:
            return True, 'mkdir', mkdir_match.group(1).strip()

        # help 命令
        if message in ['help', '帮助']:
            return True, 'help', ''

        # clear 命令
        if message in ['clear', 'reset', '清理', '重置']:
            return True, 'clear', ''

        return False, None, ''

    def is_confirmation_message(self, message: str) -> tuple[bool, Optional[str]]:
        """
        判断是否为授权确认消息

        支持简单格式: "确认"/"取消"
        支持完整格式: "confirm <id>" / "reject <id>"

        Returns:
            (is_confirmation, action)
        """
        message_lower = message.strip().lower()

        # 简单格式: 确认/取消 (单次回复)
        if message_lower in ['确认', '取消', 'confirm', 'cancel', 'yes', 'no', 'y', 'n']:
            return True, 'simple'

        # 完整格式: confirm/reject <request_id>
        if message_lower.startswith('confirm ') or message_lower.startswith('批准 '):
            return True, 'confirm'
        elif message_lower.startswith('reject ') or message_lower.startswith('拒绝 '):
            return True, 'reject'

        return False, None

    def handle_command(self, chat_id: str, command_type: str, args: str) -> str:
        """处理控制命令，返回命令执行结果"""

        # 项目管理命令
        if command_type == 'projects':
            current_dir = self.get_working_dir(chat_id)
            return self.project_manager.format_list(current_path=current_dir)

        elif command_type == 'use':
            # 切换到项目
            project = self.project_manager.get(args)
            if not project:
                # 尝试搜索
                results = self.project_manager.search(args)
                if results:
                    if len(results) == 1:
                        project = results[0]
                    else:
                        return f"❌ 找到多个匹配的项目：\n\n{self.project_manager.format_list(results)}"
                else:
                    return f"❌ 项目不存在：{args}\n\n使用 `projects` 查看所有项目"

            success, message = self.set_working_dir(chat_id, project.path)
            if success:
                return f"✅ 已切换到项目：{project.name}\n{message}\n\n描述：{project.description or '无描述'}"
            else:
                return message

        elif command_type == 'addproj':
            # 添加项目
            parts = args.split()
            if len(parts) < 2:
                return "❌ 格式错误，使用：addproj <名称> <路径> [别名...]"

            name = parts[0]
            path = parts[1]
            alias = parts[2:] if len(parts) > 2 else []

            success, message = self.project_manager.add(name, path, alias)
            return message

        elif command_type == 'delproj':
            # 删除项目
            success, message = self.project_manager.remove(args)
            return message

        elif command_type == 'search':
            # 搜索项目
            results = self.project_manager.search(args)
            if not results:
                return f"❌ 没有找到匹配 '{args}' 的项目"
            return self.project_manager.format_list(results)

        # 目录管理命令
        elif command_type == 'cd':
            success, message = self.set_working_dir(chat_id, args)
            return message

        elif command_type == 'pwd':
            working_dir = self.get_working_dir(chat_id)
            return f"📁 当前工作目录：{working_dir}"

        elif command_type == 'ls':
            # 列出目录内容
            target_path = args if args else self.get_working_dir(chat_id)

            # 展开波浪号
            target_path = os.path.expanduser(target_path)

            # 转换为绝对路径
            if not os.path.isabs(target_path):
                current_dir = self.get_working_dir(chat_id)
                target_path = os.path.abspath(os.path.join(current_dir, target_path))

            # 验证路径存在
            if not os.path.exists(target_path):
                return f"❌ 路径不存在：{target_path}"

            # 如果是文件，显示文件信息
            if os.path.isfile(target_path):
                return f"📄 {target_path}"

            # 列出目录内容
            try:
                entries = os.listdir(target_path)
                if not entries:
                    return f"📁 {target_path}\n(空目录)"

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

                return result
            except PermissionError:
                return f"❌ 无权限访问：{target_path}"
            except Exception as e:
                return f"❌ 列出目录失败：{str(e)}"

        elif command_type == 'mkdir':
            # 创建目录
            dir_name = args

            # 展开波浪号
            dir_name = os.path.expanduser(dir_name)

            # 转换为绝对路径
            if not os.path.isabs(dir_name):
                current_dir = self.get_working_dir(chat_id)
                dir_name = os.path.abspath(os.path.join(current_dir, dir_name))

            # 检查是否已存在
            if os.path.exists(dir_name):
                return f"❌ 路径已存在：{dir_name}"

            # 检查父目录权限
            parent_dir = os.path.dirname(dir_name)
            if parent_dir and not os.access(parent_dir, os.W_OK):
                return f"❌ 无权限在 {parent_dir} 中创建目录"

            # 创建目录
            try:
                os.makedirs(dir_name, exist_ok=False)
                return f"✅ 目录已创建：{dir_name}"
            except Exception as e:
                return f"❌ 创建目录失败：{str(e)}"

        elif command_type == 'clear':
            # 清理未处理消息和对话历史
            cleared_items = []

            # 1. 清理消息队列文件
            if os.path.exists(MESSAGE_FILE):
                try:
                    # 获取消息数量
                    with open(MESSAGE_FILE, 'r') as f:
                        msg_count = sum(1 for line in f if line.strip())

                    # 清空文件
                    open(MESSAGE_FILE, 'w').close()
                    cleared_items.append(f"消息队列 ({msg_count} 条)")
                except Exception as e:
                    return f"❌ 清理消息队列失败：{str(e)}"

            # 2. 清理当前聊天的对话历史
            if chat_id in self.conversation_history:
                history_count = len(self.conversation_history[chat_id])
                del self.conversation_history[chat_id]
                cleared_items.append(f"对话历史 ({history_count} 条)")

            # 3. 可选：清理已处理记录（保留最近100条）
            if os.path.exists(PROCESSED_FILE):
                try:
                    with open(PROCESSED_FILE, 'r') as f:
                        lines = f.readlines()

                    if len(lines) > 100:
                        # 保留最近100条
                        with open(PROCESSED_FILE, 'w') as f:
                            f.writelines(lines[-100:])
                        cleared_items.append(f"已处理记录 (保留最近100条)")
                except Exception as e:
                    return f"❌ 清理已处理记录失败：{str(e)}"

            if cleared_items:
                return f"✅ 已清理：\n" + "\n".join(f"  • {item}" for item in cleared_items) + "\n\n对话已重置到干净状态"
            else:
                return "✅ 无需清理，已经是干净状态"

        elif command_type == 'help':
            return """🤖 飞书Claude Bot 控制命令

📁 项目管理：
  projects / proj           列出所有项目
  use <项目名或别名>         切换到指定项目
  search <关键词>           搜索项目
  addproj <名称> <路径>     添加新项目
  delproj <项目名>          删除项目

📂 目录管理：
  cd <path>                 切换工作目录
  pwd                       显示当前工作目录
  ls [path]                 列出目录内容
  mkdir <path>              创建新目录

🔄 状态管理：
  clear / reset             清理未处理消息和历史记录

💡 使用示例：
  projects                  查看所有项目
  use openclaw              切换到 openclaw 项目
  use oc                   使用别名切换
  search bot               搜索包含 "bot" 的项目
  addproj myapp ~/projects/my-app  添加新项目
  cd ~/projects             切换到项目目录
  cd ..                    返回上级目录
  pwd                      查看当前目录
  ls                       列出当前目录
  clear                    清理所有待处理消息"""

        return "❌ 未知命令"

    def _acquire_lock(self):
        """获取处理锁，防止重复处理"""
        lock_file = "/tmp/feishu_bot_processing.lock"
        try:
            self.processing_lock = open(lock_file, 'w')
            fcntl.flock(self.processing_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (IOError, OSError):
            return False

    def _release_lock(self):
        """释放处理锁"""
        if self.processing_lock:
            try:
                fcntl.flock(self.processing_lock.fileno(), fcntl.LOCK_UN)
                self.processing_lock.close()
            except:
                pass
            self.processing_lock = None

    def process_messages(self):
        """处理新消息"""
        if not os.path.exists(MESSAGE_FILE):
            return

        # 尝试获取处理锁，如果获取失败说明有其他进程正在处理
        if not self._acquire_lock():
            print("[跳过] 已有进程在处理消息")
            return

        try:
            with open(MESSAGE_FILE, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        msg = json.loads(line)
                        message_id = msg.get('message_id')

                        # 跳过无效消息（缺少必需字段）
                        if not message_id:
                            print(f"[跳过] 无效消息（缺少 message_id）: {line.strip()[:100]}")
                            continue

                        # 跳过已处理的消息
                        if message_id in self.processed_ids:
                            continue

                        # 解析消息
                        sender_id = msg.get('sender_id')
                        chat_id = msg.get('chat_id')
                        content_str = msg.get('content', '')
                        text_content = self.parse_content(content_str)

                        print(f"\n{'='*60}")
                        print(f"📱 收到新消息")
                        print(f"发送者: {sender_id}")
                        print(f"聊天ID: {chat_id}")
                        print(f"内容: {text_content}")
                        print(f"{'='*60}\n")

                        # 解析消息后，立即发送reaction
                        emoji_type = ReactionSelector.select_emoji_type(text_content)
                        self.feishu.send_reaction(message_id, emoji_type)

                        # 检查是否为授权确认消息
                        is_confirm, confirm_action = self.is_confirmation_message(text_content)
                        if is_confirm:
                            print(f"[🔐] 检测到授权确认消息: {confirm_action}")
                            approved, message, auth_req = self.auth_manager.handle_confirmation(
                                sender_id, text_content, chat_id
                            )

                            # 发送确认结果
                            self.feishu.send_message(chat_id, message)

                            # 如果批准，执行原命令
                            if approved and auth_req:
                                response = self.handle_command(
                                    auth_req.chat_id, auth_req.command, auth_req.args
                                )
                                self.feishu.send_message(chat_id, response)

                                # 记录审计日志
                                self.auth_manager.audit_logger.log_operation(
                                    sender_id=auth_req.sender_id,
                                    chat_id=auth_req.chat_id,
                                    command=auth_req.command,
                                    args=auth_req.args,
                                    operation_type=auth_req.operation_type,
                                    status="success",
                                    result=response[:100]
                                )

                            self.save_processed_id(message_id)
                            print("✅ 授权确认处理完成\n")
                            continue

                        # 检查是否为控制命令
                        is_cmd, cmd_type, cmd_args = self.parse_command(text_content)
                        if is_cmd:
                            print(f"[🎛️] 检测到控制命令: {cmd_type} {cmd_args}")

                            # 授权检查
                            can_execute, auth_message, auth_req = self.auth_manager.process_command(
                                sender_id, chat_id, cmd_type, cmd_args
                            )

                            if not can_execute:
                                # 需要授权或权限不足
                                self.feishu.send_message(chat_id, auth_message)
                                self.save_processed_id(message_id)
                                print(f"[🔒] {auth_message}\n")
                                continue

                            # 有权限且无需授权，继续执行命令
                            response = self.handle_command(chat_id, cmd_type, cmd_args)

                            # 记录审计日志
                            op_type = COMMAND_PERMISSIONS.get(cmd_type).operation_type
                            self.auth_manager.audit_logger.log_operation(
                                sender_id=sender_id,
                                chat_id=chat_id,
                                command=cmd_type,
                                args=cmd_args,
                                operation_type=op_type,
                                status="success",
                                result=response[:100]
                            )

                            # 发送命令结果
                            success = self.feishu.send_message(chat_id, response)
                            if success:
                                self.save_processed_id(message_id)
                                print("✅ 命令处理完成\n")

                            # 如果是 clear 命令，直接退出当前批次处理
                            if cmd_type == 'clear':
                                print("[清理] 检测到 clear 命令，跳过当前批次剩余消息\n")
                                break  # 退出 for 循环，不再处理已读取的其他消息

                            continue  # 跳过Claude CLI调用

                        # 设置当前chat_id的工作目录
                        current_working_dir = self.get_working_dir(chat_id)
                        self.claude.set_working_dir(current_working_dir)
                        print(f"[📁] 工作目录: {current_working_dir}")

                        # 获取对话历史
                        history = self.get_conversation_history(chat_id)

                        # 检测首次对话
                        is_first_conversation = len(history) == 0
                        if is_first_conversation:
                            print("[🎉] 检测到首次对话")

                        # 尝试使用卡片流式更新
                        # 1. 创建并发送卡片（返回message_id）
                        message_id_for_card = self.feishu.create_and_send_card(chat_id, "🤖 正在思考...")

                        if message_id_for_card:
                            # 2. 定义更新回调
                            def update_card(content: str):
                                self.feishu.update_card_message(message_id_for_card, content)

                            # 3. 节流更新器（0.5秒间隔）
                            updater = ThrottledUpdater(update_card, interval=0.5)

                            # 4. 流式处理
                            response = self.claude.chat_streaming(
                                text_content,
                                lambda c: updater.update(c),
                                conversation_history=history,
                                timeout=300  # 5分钟超时（复杂查询需要联网搜索）
                            )

                            # 5. 最终更新
                            if response:
                                # 检查内容是否超过卡片限制
                                card_max_length = 2800

                                if len(response) <= card_max_length:
                                    # 内容较短，用卡片完整显示
                                    updater.force_update(response)
                                    print(f"[✅] 卡片更新完成，内容长度: {len(response)}")
                                else:
                                    # 内容过长，卡片显示前半部分，剩余部分用文本消息继续发送
                                    card_content = response[:card_max_length] + "\n\n...（内容过长，剩余部分将在下条消息继续）"
                                    updater.force_update(card_content)
                                    print(f"[⚠️] 内容过长（{len(response)}字符），卡片显示{card_max_length}字符，剩余部分用文本消息发送")

                                    # 延迟后发送剩余内容
                                    time.sleep(0.5)
                                    remaining_content = response[card_max_length:]

                                    # 尝试在剩余内容开头添加续接标记
                                    # 找到合适的分割点（段落开头）
                                    if not remaining_content.startswith('\n'):
                                        # 如果不是从新段落开始，查找最近的段落分割
                                        newline_pos = remaining_content.find('\n\n')
                                        if newline_pos > 0 and newline_pos < 200:
                                            remaining_content = remaining_content[newline_pos + 2:]

                                    # 分段发送剩余内容
                                    sent_parts = self.feishu.send_long_content(chat_id, remaining_content)
                                    print(f"[✅] 继续发送了 {sent_parts} 条消息")

                                # 保存到对话历史
                                self.add_to_history(chat_id, "user", text_content)
                                self.add_to_history(chat_id, "assistant", response)

                                # 标记为已处理
                                self.save_processed_id(message_id)
                                print("\n✅ 消息处理完成（卡片模式）\n")
                            else:
                                # 失败时更新卡片显示错误
                                update_success = self.feishu.update_card_message(
                                    message_id_for_card,
                                    "❌ Claude CLI调用失败（超时或异常）\n\n请稍后重试或发送「clear」清理队列。"
                                )
                                if not update_success:
                                    print("[警告] 卡片错误消息更新失败")

                                # 标记为已处理，避免重复处理
                                self.save_processed_id(message_id)
                                print("\n❌ Claude CLI调用失败\n")
                        else:
                            # 回退到普通消息模式
                            print("[回退] 卡片创建失败，使用普通消息模式")
                            self.feishu.send_message(chat_id, "🔄 正在处理...")

                            response = self.claude.chat(text_content, history, timeout=300)  # 5分钟超时

                            if response:
                                # 使用分段发送处理长内容
                                sent_parts = self.feishu.send_long_content(chat_id, response)

                                if sent_parts > 0:
                                    # 保存到对话历史
                                    self.add_to_history(chat_id, "user", text_content)
                                    self.add_to_history(chat_id, "assistant", response)

                                    # 标记为已处理
                                    self.save_processed_id(message_id)
                                    print("\n✅ 消息处理完成（普通模式）\n")
                                else:
                                    # 发送失败，但仍标记为已处理避免重复
                                    self.save_processed_id(message_id)
                                    print("\n❌ 发送回复失败（已标记处理）\n")
                            else:
                                # Claude调用失败，标记为已处理避免重复
                                self.save_processed_id(message_id)
                                print("\n❌ Claude CLI调用失败（已标记处理）\n")

                        # 短暂延迟，避免过度消耗资源
                        time.sleep(0.5)

                    except json.JSONDecodeError as e:
                        print(f"[错误] JSON解析失败: {str(e)}")
                        continue
                    except Exception as e:
                        print(f"[错误] 处理消息异常: {str(e)}")
                        continue

        except Exception as e:
            print(f"[错误] 读取消息文件失败: {str(e)}")
        finally:
            # 释放处理锁
            self._release_lock()

    def run(self):
        """运行消息处理循环"""
        print("="*60)
        print("🚀 飞书-Claude本地CLI自动化Bot")
        print("="*60)
        print(f"消息文件: {MESSAGE_FILE}")
        print(f"已处理记录: {PROCESSED_FILE}")
        print(f"Claude CLI: {CLAUDE_CLI_PATH}")
        print(f"工作目录: {WORKING_DIR}")
        print("="*60)
        print()

        # 检查Claude CLI是否存在
        if not os.path.exists(CLAUDE_CLI_PATH):
            print(f"❌ 错误: 找不到Claude CLI: {CLAUDE_CLI_PATH}")
            print("\n请确保Claude CLI已安装并路径正确。\n")
            print("检查Claude CLI路径:")
            print("  which claude")
            return

        # 加载已处理的消息ID
        self.load_processed_ids()
        print(f"✅ 已加载 {len(self.processed_ids)} 条已处理消息记录\n")

        # 监控循环
        check_interval = 1  # 每1秒检查一次
        print(f"👀 开始监听新消息 (检查间隔: {check_interval}秒)\n")

        last_size = 0
        if os.path.exists(MESSAGE_FILE):
            last_size = os.path.getsize(MESSAGE_FILE)

        while True:
            try:
                # 检查消息文件是否有更新
                if os.path.exists(MESSAGE_FILE):
                    current_size = os.path.getsize(MESSAGE_FILE)

                    # 文件大小变化（变大或变小）都需要处理
                    if current_size != last_size:
                        if current_size > 0:
                            print(f"🔔 检测到新消息...")
                            self.process_messages()
                        last_size = current_size

                time.sleep(check_interval)

            except KeyboardInterrupt:
                print("\n\n👋 Bot已停止")
                break
            except Exception as e:
                print(f"[错误] 监控循环异常: {str(e)}")
                time.sleep(check_interval)


# ==================== 主程序 ====================

def main():
    """主函数"""
    processor = MessageProcessor()
    processor.run()


if __name__ == "__main__":
    main()
