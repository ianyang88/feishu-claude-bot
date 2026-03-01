#!/usr/bin/env node

/**
 * 模拟接收飞书消息
 * 用于测试MCP工具的接收功能
 */

const feishuClient = require('./dist/feishuClient.js');
const messageQueue = require('./dist/utils/messageQueue.js');

// 模拟一条消息
const testMessage = {
  message_id: 'test_msg_' + Date.now(),
  sender_id: 'ou_test_user_123',
  sender_type: 'user',
  message_type: 'text',
  content: '{"text":"这是一条测试消息：你好，飞书MCP服务！"}',
  chat_id: 'oc_test_chat_456',
  timestamp: Date.now(),
  read: false
};

console.log('================================');
console.log('模拟飞书消息接收');
console.log('================================');
console.log('');
console.log('模拟消息:');
console.log(JSON.stringify(testMessage, null, 2));
console.log('');

// 在实际使用中，你需要通过以下方式接收消息：
// 1. 配置飞书事件订阅（Webhook或长连接）
// 2. 或者手动调用feishu_get_messages工具

console.log('📝 说明:');
console.log('   在Claude Desktop中使用以下命令：');
console.log('');
console.log('   1. 查看消息:');
console.log('      调用 feishu_get_messages 工具');
console.log('');
console.log('   2. 发送消息:');
console.log('      调用 feishu_send_message 工具');
console.log('      参数:');
console.log('      - receive_id: "用户的open_id"');
console.log('      - receive_id_type: "open_id"');
console.log('      - message_type: "text"');
console.log('      - content: "{\"text\":\"消息内容\"}"');
console.log('');
console.log('================================');
