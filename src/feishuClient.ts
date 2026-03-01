import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import { MessageQueue } from './utils/messageQueue.js';
import { FeishuMessage, SendMessageParams, ConnectionStatus } from './types/index.js';

/**
 * 飞书API客户端
 * 使用HTTP轮询方式（更稳定可靠）
 */
export class FeishuClient {
  private messageQueue: MessageQueue;
  private config: { appId: string; appSecret: string };
  private connectionTime: Date | null = null;
  private totalSent: number = 0;
  private totalReceived: number = 0;
  private tenantAccessToken: string | null = null;
  private tokenExpireTime: number = 0;
  private pollInterval: NodeJS.Timeout | null = null;
  private lastMessageTimestamp: string = '';
  private messageFilePath = '/tmp/feishu_messages.jsonl';
  private lastReadPosition = 0;

  constructor(config: { appId: string; appSecret: string }, messageQueue: MessageQueue) {
    this.config = config;
    this.messageQueue = messageQueue;
  }

  /**
   * 获取tenant_access_token
   */
  private async getTenantAccessToken(): Promise<string> {
    // 如果token还有效，直接返回
    if (this.tenantAccessToken && Date.now() < this.tokenExpireTime) {
      return this.tenantAccessToken;
    }

    try {
      const response = await axios.post(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        {
          app_id: this.config.appId,
          app_secret: this.config.appSecret,
        }
      );

      if (response.data.code === 0) {
        this.tenantAccessToken = response.data.tenant_access_token;
        // 提前5分钟过期
        this.tokenExpireTime = Date.now() + (response.data.expire - 300) * 1000;
        console.error('[Feishu] Token refreshed successfully');
        return this.tenantAccessToken!;
      } else {
        throw new Error(`Failed to get token: ${response.data.msg}`);
      }
    } catch (error: any) {
      console.error('[Feishu] Error getting tenant access token:', error.message);
      throw error;
    }
  }

  /**
   * 启动客户端（轮询模式）
   */
  async start(): Promise<void> {
    console.error(`[Feishu] Starting client for app ${this.config.appId}...`);

    try {
      // 先获取token
      await this.getTenantAccessToken();

      this.connectionTime = new Date();
      console.error('[Feishu] Client started successfully (polling mode)');
      console.error(`[Feishu] Connected at ${this.connectionTime.toISOString()}`);

      // 启动轮询
      this.startPolling();

    } catch (error) {
      console.error('[Feishu] Failed to start client:', error);
      throw error;
    }
  }

  /**
   * 启动消息轮询
   */
  private startPolling(): void {
    // 立即执行一次
    this.pollMessages();

    // 每3秒轮询一次
    this.pollInterval = setInterval(() => {
      this.pollMessages();
    }, 3000);
  }

  /**
   * 轮询获取新消息
   */
  private async pollMessages(): Promise<void> {
    try {
      // 读取Python WebSocket服务保存的消息文件
      if (fs.existsSync(this.messageFilePath)) {
        const stats = fs.statSync(this.messageFilePath);
        const currentSize = stats.size;

        // 如果文件有新内容，读取新消息
        if (currentSize > this.lastReadPosition) {
          const content = fs.readFileSync(this.messageFilePath, 'utf-8');
          const lines = content.split('\n').filter(line => line.trim());

          // 从上次读取位置开始处理
          let processedCount = 0;
          for (let i = 0; i < lines.length; i++) {
            // 跳过已经处理过的消息（基于文件大小估算）
            const byteStart = lines.slice(0, i).join('\n').length;
            if (byteStart >= this.lastReadPosition) {
              try {
                const message = JSON.parse(lines[i]);

                // 转换为FeishuMessage格式
                const feishuMessage: FeishuMessage = {
                  message_id: message.message_id,
                  sender_id: message.sender_id,
                  sender_type: message.sender_type || 'user',
                  message_type: message.message_type || 'text',
                  content: message.content,
                  chat_id: message.chat_id,
                  timestamp: message.timestamp || Date.now(),
                  read: false
                };

                this.messageQueue.add(feishuMessage);
                this.totalReceived++;
                processedCount++;
                console.error(`[Feishu] 📨 New message from ${message.sender_id}: ${JSON.parse(message.content).text}`);
              } catch (e) {
                // 忽略解析错误
              }
            }
          }

          this.lastReadPosition = currentSize;

          if (processedCount > 0) {
            console.error(`[Feishu] ✅ Processed ${processedCount} new messages`);
          }
        }
      }
    } catch (error: any) {
      // 轮询失败不打印错误，避免日志过多
    }
  }

  /**
   * 停止客户端
   */
  stop(): void {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
      console.error('[Feishu] Client stopped');
    }
    this.connectionTime = null;
  }

  /**
   * 发送消息到飞书
   */
  async sendMessage(params: SendMessageParams): Promise<{
    success: boolean;
    message_id?: string;
    error?: string;
  }> {
    try {
      console.error('[Feishu] Sending message:', JSON.stringify(params, null, 2));

      const token = await this.getTenantAccessToken();

      const response = await axios.post(
        'https://open.feishu.cn/open-apis/im/v1/messages',
        {
          receive_id: params.receive_id,
          content: params.content,
          msg_type: params.message_type,
        },
        {
          params: {
            receive_id_type: params.receive_id_type,
          },
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.data.code === 0) {
        this.totalSent++;
        console.error('[Feishu] Message sent successfully:', response.data.data?.message_id);
        return {
          success: true,
          message_id: response.data.data?.message_id,
        };
      } else {
        console.error('[Feishu] Failed to send message:', response.data.code, response.data.msg);
        return {
          success: false,
          error: `Code: ${response.data.code}, Msg: ${response.data.msg}`,
        };
      }
    } catch (error: any) {
      console.error('[Feishu] Error sending message:', error.message);
      return {
        success: false,
        error: error.message || String(error),
      };
    }
  }

  /**
   * 获取连接状态
   */
  getStatus(): ConnectionStatus {
    return {
      connected: this.connectionTime !== null,
      connection_time: this.connectionTime?.toISOString(),
      messages_in_queue: this.messageQueue.size(),
      total_received: this.messageQueue.getTotalReceived(),
      total_sent: this.totalSent,
    };
  }

  /**
   * 测试连接（发送测试消息）
   */
  async testConnection(testUserId: string): Promise<boolean> {
    const result = await this.sendMessage({
      receive_id: testUserId,
      receive_id_type: 'open_id',
      message_type: 'text',
      content: JSON.stringify({ text: '🔔 飞书MCP服务连接测试成功！' }),
    });
    return result.success;
  }

  /**
   * 模拟接收消息（用于测试）
   * 在实际使用中，消息应该通过飞书的事件回调接收
   */
  simulateMessage(message: FeishuMessage): void {
    this.messageQueue.add(message);
    this.totalReceived++;
    console.error(`[Feishu] Simulated message added to queue. Queue size: ${this.messageQueue.size()}`);
  }
}
