/**
 * 飞书消息接口
 */
export interface FeishuMessage {
  /** 消息ID */
  message_id: string;
  /** 发送者ID */
  sender_id: string;
  /** 发送者类型: user, bot, group */
  sender_type: string;
  /** 消息类型: text, post, interactive, etc. */
  message_type: string;
  /** 消息内容 (JSON字符串或文本) */
  content: string;
  /** 聊天ID */
  chat_id: string;
  /** 时间戳 */
  timestamp: number;
  /** 是否已读 */
  read?: boolean;
}

/**
 * WebSocket连接状态
 */
export interface ConnectionStatus {
  /** 是否已连接 */
  connected: boolean;
  /** 连接建立时间 */
  connection_time?: string;
  /** 队列中消息数量 */
  messages_in_queue: number;
  /** 总接收消息数 */
  total_received: number;
  /** 总发送消息数 */
  total_sent: number;
  /** 最后错误信息 */
  last_error?: string;
}

/**
 * 发送消息参数
 */
export interface SendMessageParams {
  /** 接收者ID */
  receive_id: string;
  /** 接收者ID类型 */
  receive_id_type: 'user_id' | 'open_id' | 'chat_id' | 'email';
  /** 消息类型 */
  message_type: 'text' | 'post' | 'interactive' | 'card' | 'audio' | 'video' | 'file' | 'image' | 'sticker';
  /** 消息内容 (JSON字符串) */
  content: string;
}

/**
 * 获取消息返回值
 */
export interface GetMessagesResult {
  /** 消息列表 */
  messages: FeishuMessage[];
  /** 消息数量 */
  count: number;
}

/**
 * MCP工具响应
 */
export interface McpToolResponse {
  content: Array<{
    type: 'text';
    text: string;
  }>;
  isError?: boolean;
}

/**
 * 配置接口
 */
export interface FeishuConfig {
  app_id: string;
  app_secret: string;
  message_queue_max_size?: number;
  log_level?: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';
}
