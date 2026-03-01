#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
飞书WebSocket长连接客户端
使用Python lark-oapi SDK实现
"""

import lark_oapi as lark
import threading
import json
import time
from queue import Queue

# 配置
APP_ID = "cli_a9103ecc9fb85bd8"
APP_SECRET = "qRyCROVPjtZDjCuZqDNIPdeWteHOnVck"

# 长连接模式可以使用空字符串
ENCRYPT_KEY = ""
VERIFICATION_TOKEN = ""

# 消息队列
message_queue = Queue()

# 已处理消息ID集合（用于去重）
processed_message_ids = set()

class FeishuWebSocketClient:
    def __init__(self, app_id, app_secret):
        self.app_id = app_id
        self.app_secret = app_secret
        self.ws_client = None
        self.api_client = None
        self.running = False

    def handle_message_receive(self, data):
        """处理接收到的消息事件"""
        try:
            print(f"[Feishu] 📨 Received message event")

            # 解析消息
            event = data.event
            if event and hasattr(event, 'message'):
                message_id = event.message.message_id

                # 检查是否已处理过（去重）
                if message_id in processed_message_ids:
                    print(f"[Feishu] ⏭️  Skipping duplicate message: {message_id}")
                    return

                # 标记为已处理
                processed_message_ids.add(message_id)

                # 限制集合大小（最多保留10000条）
                if len(processed_message_ids) > 10000:
                    # 移除最旧的1000条
                    for old_id in list(processed_message_ids)[:1000]:
                        processed_message_ids.remove(old_id)

                message = {
                    'message_id': message_id,
                    'sender_id': event.sender.sender_id.open_id,
                    'sender_type': event.sender.sender_type,
                    'message_type': event.message.message_type,
                    'content': event.message.content,
                    'chat_id': event.message.chat_id,
                    'timestamp': int(time.time() * 1000),
                    'read': False
                }

                # 添加到队列
                message_queue.put(message)
                print(f"[Feishu] ✅ Message added to queue. Queue size: {message_queue.qsize()}")

                # 保存到文件供MCP服务读取
                with open('/tmp/feishu_messages.jsonl', 'a') as f:
                    f.write(json.dumps(message) + '\n')

        except Exception as e:
            print(f"[Feishu] ❌ Error handling message: {e}")

    def start(self):
        """启动WebSocket客户端"""
        print(f"[Feishu] 🚀 Starting WebSocket client for app {self.app_id}...")
        print("")

        # 创建事件处理器（长连接模式使用空字符串）
        event_handler = lark.EventDispatcherHandler.builder(
            ENCRYPT_KEY,
            VERIFICATION_TOKEN
        ).register_p2_im_message_receive_v1(self.handle_message_receive).build()

        # 创建WebSocket客户端
        self.ws_client = lark.ws.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO
        )

        # 创建API客户端（用于发送消息）
        self.api_client = lark.Client.builder() \
            .app_id(self.app_id) \
            .app_secret(self.app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        # 启动客户端
        try:
            print("正在建立WebSocket连接...")
            self.ws_client.start()
            self.running = True
            print("")
            print("=" * 60)
            print("✅ 飞书WebSocket长连接已建立！")
            print("=" * 60)
            print("")
            print("📡 连接状态: 已连接到飞书开放平台")
            print("📱 应用ID: " + self.app_id)
            print("")
            print("🎯 下一步操作:")
            print("   1. 访问飞书开放平台")
            print("      https://open.feishu.cn/app/cli_a9103ecc9fb85bd8")
            print("")
            print("   2. 进入 事件订阅")
            print("")
            print("   3. 选择 订阅方式: 使用长连接接收事件")
            print("")
            print("   4. 添加事件: im.message.receive_v1")
            print("")
            print("   5. 点击保存")
            print("")
            print("   ✨ 此时你应该能看到连接状态为: 已建立长连接")
            print("")
            print("📝 配置完成后:")
            print("   - 在飞书中发送消息")
            print("   - 消息会实时推送到此服务")
            print("")
            print("=" * 60)
            print("🔄 服务运行中... (按 Ctrl+C 停止)")
            print("=" * 60)
            print("")

        except Exception as e:
            print(f"[Feishu] ❌ Failed to start WebSocket client: {e}")
            import traceback
            traceback.print_exc()
            raise

    def stop(self):
        """停止客户端"""
        if self.ws_client:
            self.ws_client.stop()
            self.running = False
            print("[Feishu] WebSocket client stopped")

def main():
    """主函数"""
    # 创建客户端
    client = FeishuWebSocketClient(APP_ID, APP_SECRET)

    # 启动客户端（阻塞运行）
    try:
        client.start()

        # 保持运行
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[Feishu] Received interrupt signal, shutting down...")
        client.stop()
    except Exception as e:
        print(f"[Feishu] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        client.stop()

if __name__ == "__main__":
    main()
