#!/usr/bin/env python3
"""
飞书-Claude远程Shell Bot服务（新版）

基于新的架构设计：
- Shell模式：执行shell命令
- Claude模式：持久Claude CLI会话
"""

import json
import time
import os
import fcntl
from typing import Optional, Dict
from enum import Enum
from dataclasses import dataclass
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest, CreateMessageRequestBody,
    CreateMessageReactionRequest, CreateMessageReactionRequestBody
)
import requests
import random

# 导入新组件
from command_router import CommandRouter

# ==================== 配置 ====================
FEISHU_APP_ID = "cli_a9103ecc9fb85bd8"
FEISHU_APP_SECRET = "qRyCROVPjtZDjCuZqDNIPdeWteHOnVck"

# Claude CLI配置
CLAUDE_CLI_PATH = "/home/ian/.npm-global/bin/claude"
WORKING_DIR = os.path.expanduser("~/projects")

# 消息文件路径
MESSAGE_FILE = "/tmp/feishu_messages.jsonl"
PROCESSED_FILE = "/tmp/feishu_processed.jsonl"

# ==================== Reaction选择器 ====================

class ReactionSelector:
    """Reaction选择策略 - 根据消息内容智能选择emoji"""

    # 飞书预定义的emoji_type常量
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

    # 语境-emoji映射
    CONTEXT_EMOJIS = {
        "greeting": ["SMILE", "PARTY"],
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


# ==================== 飞书客户端 ====================

class FeishuClient:
    """飞书客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.tenant_access_token = None
        self.token_expire_time = 0
        self._card_update_keys = {}

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
        """给消息添加reaction"""
        try:
            client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .build()

            reaction_data = {"emoji_type": emoji_type}

            request = CreateMessageReactionRequest.builder() \
                .message_id(message_id) \
                .request_body(CreateMessageReactionRequestBody.builder()
                    .reaction_type(reaction_data)
                    .build()) \
                .build()

            response = client.im.v1.message_reaction.create(request)

            if response.code == 0:
                emoji_display = ReactionSelector.FEISHU_EMOJI_TYPES.get(emoji_type, emoji_type)
                print(f"[✅] Reaction已发送: {emoji_type} {emoji_display}")
                return True
            else:
                print(f"[❌] 发送reaction失败: code={response.code}, msg={response.msg}")
                return False

        except Exception as e:
            print(f"[错误] 发送reaction异常: {str(e)}")
            return False

    def _get_next_sequence(self, message_id: str) -> int:
        """获取并递增卡片操作序号"""
        if message_id not in self._card_sequence:
            self._card_sequence[message_id] = 0
        self._card_sequence[message_id] += 1
        return self._card_sequence[message_id]

    def _build_card_content(self, title: str, content: str, update_key: str = None) -> dict:
        """构建飞书卡片内容"""
        max_content_length = 2800
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n... (内容过长，已截断)"

        card = {
            "config": {"wide_screen_mode": True},
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

        if update_key:
            card["update_key"] = update_key

        return card

    def create_and_send_card(self, chat_id: str, content: str, title: str = "🤖 Claude") -> Optional[str]:
        """创建并发送卡片消息到聊天"""
        try:
            token = self.get_tenant_access_token()
            if not token:
                return None

            url = "https://open.feishu.cn/open-apis/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            import uuid
            update_key = f"card_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
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
                self._card_update_keys[message_id] = update_key
                print(f"[✅] 卡片消息已发送: {message_id}")
                return message_id
            else:
                print(f"[❌] 发送卡片消息失败: {data}")
                return None

        except Exception as e:
            print(f"[错误] 发送卡片消息异常: {str(e)}")
            return None

    def update_card_message(self, message_id: str, content: str, title: str = "🤖 Claude") -> bool:
        """更新卡片消息内容"""
        try:
            token = self.get_tenant_access_token()
            if not token:
                return False

            update_key = self._card_update_keys.get(message_id)
            if not update_key:
                print(f"[警告] 未找到卡片 {message_id} 的update_key")

            url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }

            card_data = self._build_card_content(title, content, update_key)
            payload = {
                "msg_type": "interactive",
                "content": json.dumps(card_data, ensure_ascii=False)
            }

            response = requests.patch(url, headers=headers, json=payload, timeout=10)
            data = response.json()

            if data.get("code") == 0:
                print(f"[✅] 卡片更新成功 (内容长度: {len(content)})")
                return True
            else:
                print(f"[❌] 更新卡片失败: {data}")
                return False

        except Exception as e:
            print(f"[错误] 更新卡片异常: {str(e)}")
            return False

    def send_long_content(self, chat_id: str, content: str) -> int:
        """分段发送长内容"""
        max_length = 3000
        sent_count = 0

        if len(content) <= max_length:
            if self.send_message(chat_id, content):
                return 1
            return 0

        # 内容过长，需要分割
        parts = []
        current_part = ""
        paragraphs = content.split('\n\n')
        current_length = 0

        for para in paragraphs:
            para_length = len(para)

            if current_length + para_length + 2 <= max_length:
                if current_part:
                    current_part += "\n\n" + para
                else:
                    current_part = para
                current_length += para_length + 2
            else:
                if current_part:
                    parts.append(current_part)
                current_part = para
                current_length = para_length

        if current_part:
            parts.append(current_part)

        # 发送各部分
        for i, part in enumerate(parts):
            if i > 0:
                part = f"...（续）\n\n{part}"
            if i < len(parts) - 1:
                part = f"{part}\n\n...（未完待续）"

            if self.send_message(chat_id, part):
                sent_count += 1
                # 不再延迟，立即发送下一段

        print(f"[分段] 内容已分成 {len(parts)} 部分发送，成功 {sent_count} 部")
        return sent_count


# ==================== 消息处理器 ====================

class MessageProcessor:
    """消息处理器 - 使用新的CommandRouter架构"""

    def __init__(self):
        self.feishu = FeishuClient(FEISHU_APP_ID, FEISHU_APP_SECRET)
        self.router = CommandRouter(CLAUDE_CLI_PATH, WORKING_DIR)
        self.processed_ids = set()
        self.processing_lock = None

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
        """保存已处理的消息ID"""
        try:
            temp_file = PROCESSED_FILE + ".tmp"
            with open(temp_file, 'a') as f:
                f.write(json.dumps({"message_id": message_id}) + '\n')
                f.flush()
                os.fsync(f.fileno())

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

        # 尝试获取处理锁
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

                        # 跳过无效消息
                        if not message_id:
                            print(f"[跳过] 无效消息（缺少 message_id）")
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

                        import time
                        start_time = time.time()

                        # 发送reaction
                        emoji_type = ReactionSelector.select_emoji_type(text_content)
                        self.feishu.send_reaction(message_id, emoji_type)

                        # 路由消息
                        response_type, response_content = self.router.route(
                            chat_id, sender_id, text_content
                        )

                        elapsed = time.time() - start_time
                        print(f"[⏱️] 处理耗时: {elapsed:.3f}秒\n")

                        # 根据类型发送回复
                        if response_type == "claude":
                            # Claude回复用卡片
                            self._send_claude_response(chat_id, response_content)
                        elif response_type == "shell":
                            # Shell输出用代码块
                            self.feishu.send_message(chat_id, f"```\n{response_content}\n```")
                        elif response_type == "system":
                            self.feishu.send_message(chat_id, response_content)
                        elif response_type == "error":
                            self.feishu.send_message(chat_id, response_content)

                        # 标记为已处理
                        self.save_processed_id(message_id)
                        print("✅ 消息处理完成\n")

                    except json.JSONDecodeError as e:
                        print(f"[错误] JSON解析失败: {str(e)}")
                        continue
                    except Exception as e:
                        print(f"[错误] 处理消息异常: {str(e)}")
                        continue

        except Exception as e:
            print(f"[错误] 读取消息文件失败: {str(e)}")
        finally:
            self._release_lock()

    def _send_claude_response(self, chat_id: str, content: str):
        """发送Claude响应（使用卡片）"""
        if not content:
            self.feishu.send_message(chat_id, "❌ Claude无响应")
            return

        # 尝试创建卡片
        message_id = self.feishu.create_and_send_card(chat_id, content[:500] + "...")
        if message_id:
            self.feishu.update_card_message(message_id, content)

            # 检查内容是否过长
            if len(content) > 2800:
                remaining = content[2800:]
                self.feishu.send_long_content(chat_id, remaining)
        else:
            # 回退到普通消息
            self.feishu.send_long_content(chat_id, content)

    def run(self):
        """运行消息处理循环"""
        print("="*60)
        print("🚀 飞书Claude Bot - 远程Shell模式")
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
            return

        # 加载已处理的消息ID
        self.load_processed_ids()
        print(f"✅ 已加载 {len(self.processed_ids)} 条已处理消息记录\n")

        # 监控循环
        check_interval = 0.1  # 100ms检查间隔，更快响应
        print(f"👀 开始监听新消息 (检查间隔: {check_interval}秒)\n")

        last_size = 0
        if os.path.exists(MESSAGE_FILE):
            last_size = os.path.getsize(MESSAGE_FILE)

        try:
            while True:
                if os.path.exists(MESSAGE_FILE):
                    current_size = os.path.getsize(MESSAGE_FILE)

                    if current_size != last_size:
                        if current_size > 0:
                            print(f"🔔 检测到新消息...")
                            self.process_messages()
                        last_size = current_size

                time.sleep(check_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Bot已停止")

            # 清理所有会话
            print("清理Claude会话...")
            self.router.cleanup()


# ==================== 主程序 ====================

def main():
    """主函数"""
    processor = MessageProcessor()
    processor.run()


if __name__ == "__main__":
    main()
