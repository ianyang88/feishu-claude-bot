#!/usr/bin/env node

/**
 * 飞书MCP服务 - 发送消息测试脚本
 */

const axios = require('axios');

const APP_ID = 'cli_a9103ecc9fb85bd8';
const APP_SECRET = 'qRyCROVPjtZDjCuZqDNIPdeWteHOnVck';

async function getToken() {
  const response = await axios.post(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    {
      app_id: APP_ID,
      app_secret: APP_SECRET,
    }
  );

  if (response.data.code === 0) {
    return response.data.tenant_access_token;
  } else {
    throw new Error(`获取token失败: ${response.data.msg}`);
  }
}

async function sendMessage(token, receiveId, message) {
  const response = await axios.post(
    'https://open.feishu.cn/open-apis/im/v1/messages',
    {
      receive_id: receiveId,
      content: JSON.stringify({ text: message }),
      msg_type: 'text',
    },
    {
      params: {
        receive_id_type: 'open_id',
      },
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );

  return response.data;
}

async function main() {
  console.log('================================');
  console.log('飞书MCP服务 - 发送消息测试');
  console.log('================================');
  console.log('');

  try {
    console.log('1. 获取访问令牌...');
    const token = await getToken();
    console.log('✅ Token获取成功');
    console.log('');

    // 注意：你需要提供一个真实的用户open_id
    console.log('2. 准备发送测试消息...');
    console.log('');
    console.log('⚠️  使用说明:');
    console.log('   1. 在飞书中找到你的open_id');
    console.log('   2. 运行: node test-send.mjs <你的open_id> "<消息内容>"');
    console.log('');
    console.log('   获取open_id的方法:');
    console.log('   - 在飞书个人主页查看链接');
    console.log('   - 或联系管理员查看');
    console.log('');

    const args = process.argv.slice(2);
    if (args.length >= 2) {
      const receiveId = args[0];
      const message = args[1];

      console.log(`3. 发送消息到 ${receiveId}...`);
      console.log(`   内容: "${message}"`);
      console.log('');

      const result = await sendMessage(token, receiveId, message);

      if (result.code === 0) {
        console.log('✅ 消息发送成功！');
        console.log(`   消息ID: ${result.data.message_id}`);
      } else {
        console.log('❌ 消息发送失败');
        console.log(`   错误码: ${result.code}`);
        console.log(`   错误信息: ${result.msg}`);
      }
    } else {
      console.log('⏭️  跳过发送（缺少参数）');
      console.log('');
      console.log('示例:');
      console.log('  node test-send.mjs ou_xxxxxxxxx "测试消息"');
    }

  } catch (error) {
    console.error('');
    console.error('❌ 发生错误:');
    console.error(error.message);
  }

  console.log('');
  console.log('================================');
}

main();
