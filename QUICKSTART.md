# 飞书MCP服务 - 快速开始指南

## 🎉 项目已成功编译!

你的飞书WebSocket长连接MCP服务已经准备就绪！

## 📋 后续步骤

### 1. 创建飞书应用

访问 [飞书开放平台](https://open.feishu.cn/app)，创建**企业自建应用**：

#### 1.1 启用机器人能力
- 进入**应用能力** → **机器人** → 点击**开启**
- 为机器人设置名称和头像

#### 1.2 配置权限
进入**权限管理**，添加以下权限：
- `im:message` - 接收和发送消息
- `im:message:group_at_msg` - 群组@消息
- `im:chat` - 访问聊天信息

#### 1.3 配置事件订阅（关键！）
进入**事件订阅**页面：
1. ✅ **选择"使用长连接接收事件"**
2. 点击**添加事件**，勾选：
   - `im.message.receive_v1` （接收消息）
3. 点击**保存**

#### 1.4 获取凭证
进入**凭证与基础信息**，复制：
- **App ID**
- **App Secret**

### 2. 配置环境变量

```bash
# 在项目根目录创建.env文件
cp .env.example .env

# 编辑.env文件，填入你的凭证
nano .env  # 或使用其他编辑器
```

填入：
```env
FEISHU_APP_ID=cli_xxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxx
```

### 3. 测试MCP服务

```bash
# 启动服务
npm start

# 在另一个终端，使用MCP Inspector测试
npx @modelcontextprotocol/inspector dist/index.js
```

你应该能看到：
```
[Feishu MCP] Starting server...
[Feishu MCP] App ID: cli_xxxxxxxxxxxxx
[Feishu MCP] Queue max size: 100
[Feishu] Starting WebSocket client for app cli_xxxxxxxxxxxxx...
[Feishu] WebSocket client started successfully
[Feishu] Connected at 2026-02-23T...
[Feishu MCP] MCP server running on stdio
[Feishu MCP] Ready to receive requests
```

### 4. 配置Claude Desktop

#### 4.1 找到配置文件
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### 4.2 添加MCP服务器
```json
{
  "mcpServers": {
    "feishu": {
      "command": "node",
      "args": [
        "/mnt/c/Users/Admin/feishu-mcp-server/dist/index.js"
      ],
      "env": {
        "FEISHU_APP_ID": "你的App ID",
        "FEISHU_APP_SECRET": "你的App Secret"
      }
    }
  }
}
```

**注意**: 修改路径为实际项目路径！

### 5. 发布飞书应用

1. 返回飞书开放平台
2. 进入**版本管理与发布**
3. 点击**创建版本**
4. 填写版本信息，点击**保存**
5. 点击**申请发布** → **发布到本企业**

### 6. 在飞书中添加机器人

1. 打开飞书客户端
2. 搜索你的机器人名称
3. 添加到联系人或群组
4. 发送测试消息："你好"

### 7. 与Claude对话

重启Claude Desktop，然后你就可以这样使用：

```
你: 检查飞书有没有新消息
Claude: [调用feishu_get_messages工具]
Claude: 收到了一条消息："你好"

你: 回复"你好！有什么可以帮助你的吗？"
Claude: [调用feishu_send_message工具]
Claude: 已发送回复到飞书
```

## 🔧 故障排查

### 问题1: WebSocket连接失败
**解决方案**:
1. 检查App ID和App Secret是否正确
2. 确认选择了"使用长连接接收事件"
3. 检查网络是否能访问飞书API

### 问题2: 收不到消息
**解决方案**:
1. 确认已添加`im.message.receive_v1`事件
2. 检查应用权限是否正确配置
3. 确认应用已发布
4. 在飞书中重新添加机器人

### 问题3: Claude无法调用工具
**解决方案**:
1. 检查Claude Desktop配置文件路径是否正确
2. 确认.env文件中的凭证正确
3. 重启Claude Desktop
4. 查看Claude Desktop日志

## 📚 MCP工具说明

### feishu_get_messages
获取飞书推送的新消息（会清空队列）

### feishu_send_message
发送消息到飞书
- `receive_id`: 接收者ID
- `receive_id_type`: ID类型（user_id/open_id/chat_id）
- `message_type`: 消息类型（text/post/interactive）
- `content`: 消息内容（JSON字符串）

### feishu_get_status
查看WebSocket连接状态和统计信息

## 🎯 使用示例

### 示例1: 简单对话
```
你: 查看飞书消息
Claude: [收到消息] 用户说："帮我分析这个数据"
你: 回复"好的，请把数据发给我"
```

### 示例2: 群组协作
```
你: 飞书群里有什么新消息？
Claude: [收到3条消息]
     1. 张三：会议改到下午3点
     2. 李四：收到
     3. 王五：好的
你: 在群里回复"收到，我会准时参加"
```

### 示例3: 查看状态
```
你: 检查飞书连接状态
Claude: WebSocket连接正常
     - 已连接时长: 2小时30分
     - 队列中消息: 0
     - 总接收: 45条
     - 总发送: 42条
```

## 🚀 下一步

- [ ] 添加更多消息类型支持（卡片、富文本等）
- [ ] 实现消息历史记录
- [ ] 添加多用户支持
- [ ] 实现自动回复功能
- [ ] 添加消息过滤和关键词检测

## 📞 获取帮助

- [飞书开放平台文档](https://open.feishu.cn/document)
- [MCP协议文档](https://modelcontextprotocol.io)
- [项目README](./README.md)

祝使用愉快！🎊
