import { FeishuMessage } from '../types/index.js';

/**
 * 消息队列管理器
 * 用于缓存飞书推送的消息，提供线程安全的消息存取
 */
export class MessageQueue {
  private queue: FeishuMessage[] = [];
  private maxSize: number;
  private totalReceived: number = 0;

  constructor(maxSize: number = 100) {
    this.maxSize = maxSize;
  }

  /**
   * 添加消息到队列
   */
  add(message: FeishuMessage): void {
    this.totalReceived++;
    this.queue.push(message);

    // 如果超过最大长度，移除最旧的消息
    if (this.queue.length > this.maxSize) {
      this.queue.shift();
    }
  }

  /**
   * 获取所有消息并清空队列
   */
  getAll(): FeishuMessage[] {
    const messages = [...this.queue];
    this.queue = [];
    return messages;
  }

  /**
   * 获取指定数量的消息（不移除）
   */
  peek(count: number = 10): FeishuMessage[] {
    return this.queue.slice(-count);
  }

  /**
   * 获取最新的一条消息（不移除）
   */
  getLatest(): FeishuMessage | null {
    if (this.queue.length === 0) {
      return null;
    }
    return this.queue[this.queue.length - 1];
  }

  /**
   * 清空队列
   */
  clear(): void {
    this.queue = [];
  }

  /**
   * 获取队列长度
   */
  size(): number {
    return this.queue.length;
  }

  /**
   * 获取总接收消息数
   */
  getTotalReceived(): number {
    return this.totalReceived;
  }

  /**
   * 根据消息ID查找消息
   */
  findById(messageId: string): FeishuMessage | null {
    return this.queue.find(msg => msg.message_id === messageId) || null;
  }

  /**
   * 获取指定聊天ID的所有消息
   */
  getByChatId(chatId: string): FeishuMessage[] {
    return this.queue.filter(msg => msg.chat_id === chatId);
  }

  /**
   * 获取指定发送者的所有消息
   */
  getBySenderId(senderId: string): FeishuMessage[] {
    return this.queue.filter(msg => msg.sender_id === senderId);
  }

  /**
   * 标记消息为已读
   */
  markAsRead(messageId: string): boolean {
    const message = this.findById(messageId);
    if (message) {
      message.read = true;
      return true;
    }
    return false;
  }

  /**
   * 获取队列统计信息
   */
  getStats(): {
    size: number;
    totalReceived: number;
    maxSize: number;
    oldestMessage?: FeishuMessage;
    newestMessage?: FeishuMessage;
  } {
    return {
      size: this.queue.length,
      totalReceived: this.totalReceived,
      maxSize: this.maxSize,
      oldestMessage: this.queue[0],
      newestMessage: this.queue[this.queue.length - 1],
    };
  }
}
