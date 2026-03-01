#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import { FeishuClient } from './feishuClient.js';
import { MessageQueue } from './utils/messageQueue.js';
import {
  GetMessagesResult,
  SendMessageParams,
  McpToolResponse,
  ConnectionStatus,
} from './types/index.js';

/**
 * 飞书MCP服务器
 * 通过WebSocket长连接实现Claude与飞书的双向通信
 */

// 从环境变量获取配置
const APP_ID = process.env.FEISHU_APP_ID || '';
const APP_SECRET = process.env.FEISHU_APP_SECRET || '';
const QUEUE_MAX_SIZE = parseInt(process.env.MESSAGE_QUEUE_MAX_SIZE || '100', 10);

// 验证配置
if (!APP_ID || !APP_SECRET) {
  console.error('[Error] FEISHU_APP_ID and FEISHU_APP_SECRET must be set');
  console.error('[Error] Please set these environment variables or create a .env file');
  process.exit(1);
}

// 创建消息队列
const messageQueue = new MessageQueue(QUEUE_MAX_SIZE);

// 创建飞书客户端
const feishuClient = new FeishuClient(
  { appId: APP_ID, appSecret: APP_SECRET },
  messageQueue
);

// 创建MCP服务器
const server = new Server(
  {
    name: 'feishu-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// 注册工具列表
server.setRequestHandler(ListToolsRequestSchema, async () => {
  const tools: Tool[] = [
    {
      name: 'feishu_get_messages',
      description:
        '获取飞书推送的新消息。返回从上次调用以来收到的所有消息，并清空消息队列。',
      inputSchema: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
    {
      name: 'feishu_send_message',
      description:
        '向飞书用户或群组发送消息。支持文本、富文本、卡片等多种消息类型。',
      inputSchema: {
        type: 'object',
        properties: {
          receive_id: {
            type: 'string',
            description: '接收者ID（用户ID、Open ID或群组ID）',
          },
          receive_id_type: {
            type: 'string',
            enum: ['user_id', 'open_id', 'chat_id', 'email'],
            description: '接收者ID类型',
          },
          message_type: {
            type: 'string',
            enum: ['text', 'post', 'interactive', 'card', 'audio', 'video', 'file', 'image', 'sticker'],
            description: '消息类型',
          },
          content: {
            type: 'string',
            description:
              '消息内容（JSON字符串格式）。\n' +
              '文本消息示例: {"text":"消息内容"}\n' +
              '卡片消息示例: {"type":"template","data":{"template_id":"xxx","template_variable":{...}}}',
          },
        },
        required: ['receive_id', 'receive_id_type', 'message_type', 'content'],
      },
    },
    {
      name: 'feishu_get_status',
      description: '获取WebSocket连接状态和消息队列统计信息',
      inputSchema: {
        type: 'object',
        properties: {},
        required: [],
      },
    },
  ];
  return { tools };
});

// 注册工具调用处理器
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'feishu_get_messages': {
        const messages = messageQueue.getAll();
        const result: GetMessagesResult = {
          messages,
          count: messages.length,
        };

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'feishu_send_message': {
        const params = args as unknown as SendMessageParams;

        // 验证参数
        if (!params.receive_id || !params.receive_id_type || !params.message_type || !params.content) {
          return {
            content: [
              {
                type: 'text',
                text: '错误: 缺少必要参数 (receive_id, receive_id_type, message_type, content)',
              },
            ],
            isError: true,
          };
        }

        // 发送消息
        const result = await feishuClient.sendMessage(params);

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(result, null, 2),
            },
          ],
        };
      }

      case 'feishu_get_status': {
        const status = feishuClient.getStatus();
        const stats = messageQueue.getStats();

        const fullStatus = {
          ...status,
          queue_stats: stats,
        };

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(fullStatus, null, 2),
            },
          ],
        };
      }

      default:
        return {
          content: [
            {
              type: 'text',
              text: `未知工具: ${name}`,
            },
          ],
          isError: true,
        };
    }
  } catch (error: any) {
    console.error(`[Error] Tool execution failed: ${name}`, error);
    return {
      content: [
        {
          type: 'text',
          text: `工具执行错误: ${error.message || String(error)}`,
        },
      ],
      isError: true,
    };
  }
});

/**
 * 主函数
 */
async function main() {
  console.error('[Feishu MCP] Starting server...');
  console.error(`[Feishu MCP] App ID: ${APP_ID}`);
  console.error(`[Feishu MCP] Queue max size: ${QUEUE_MAX_SIZE}`);

  try {
    // 启动飞书WebSocket客户端
    await feishuClient.start();

    // 设置stdio传输
    const transport = new StdioServerTransport();
    await server.connect(transport);

    console.error('[Feishu MCP] MCP server running on stdio');
    console.error('[Feishu MCP] Ready to receive requests');
  } catch (error) {
    console.error('[Feishu MCP] Failed to start server:', error);
    process.exit(1);
  }
}

/**
 * 优雅退出处理
 */
process.on('SIGINT', () => {
  console.error('[Feishu MCP] Received SIGINT, shutting down...');
  feishuClient.stop();
  process.exit(0);
});

process.on('SIGTERM', () => {
  console.error('[Feishu MCP] Received SIGTERM, shutting down...');
  feishuClient.stop();
  process.exit(0);
});

process.on('uncaughtException', (error) => {
  console.error('[Feishu MCP] Uncaught exception:', error);
  feishuClient.stop();
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('[Feishu MCP] Unhandled rejection at:', promise, 'reason:', reason);
});

// 启动服务器
main().catch((error) => {
  console.error('[Feishu MCP] Fatal error:', error);
  process.exit(1);
});
