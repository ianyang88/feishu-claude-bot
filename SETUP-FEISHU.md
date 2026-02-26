# 🔧 飞书应用配置指南

## ⚠️ 当前状态

服务已成功启动并运行，但WebSocket连接返回404错误。这是因为飞书应用还没有启用长连接功能。

## 📋 必须完成的配置

### 步骤1: 访问飞书开放平台

访问链接：https://open.feishu.cn/app/cli_a9103ecc9fb85bd8

### 步骤2: 启用机器人能力

1. 点击左侧菜单 **"应用能力"**
2. 找到 **"机器人"**，点击 **"开启"**
3. 设置机器人名称和头像
4. 点击 **"确定"**

### 步骤3: 配置权限（重要！）

1. 点击左侧菜单 **"权限管理"**
2. 点击 **"添加权限"**，搜索并添加以下权限：

```
im:message                    (必需 - 接收和发送消息)
im:message:group_at_msg       (群组@消息)
im:chat                       (访问聊天信息)
```

3. 点击 **"批量申请权限"**
4. 等待权限审核通过（通常立即生效）

### 步骤4: 配置事件订阅（关键！）

1. 点击左侧菜单 **"事件订阅"**
2. **重要**: 选择 **"使用长连接接收事件"** ⭐
3. 点击 **"添加事件"**
4. 勾选以下事件：
   ```
   im.message.receive_v1  (接收消息事件 - 必需)
   ```
5. 点击 **"保存"**

### 步骤5: 发布应用

1. 点击左侧菜单 **"版本管理与发布"**
2. 点击 **"创建版本"**
3. 填写版本信息：
   - 版本号：`1.0.0`
   - 版本说明：`飞书MCP机器人`
4. 点击 **"保存"**
5. 点击 **"申请发布"**
6. 选择 **"发布到本企业"**
7. 点击 **"确定"**

### 步骤6: 验证配置

完成上述配置后，返回飞书开放平台的应用首页，检查：

- ✅ 机器人状态：已启用
- ✅ 事件订阅：已启用长连接
- ✅ 应用状态：已发布

## 🔄 配置完成后重启服务

完成飞书配置后，重新启动服务：

```bash
cd /mnt/c/Users/Admin/feishu-mcp-server
export FEISHU_APP_ID=cli_a9103ecc9fb85bd8
export FEISHU_APP_SECRET=qRyCROVPjtZDjCuZqDNIPdeWteHOnVck
npm start
```

### 预期成功输出

```
[Feishu MCP] Starting server...
[Feishu MCP] App ID: cli_a9103ecc9fb85bd8
[Feishu MCP] Queue max size: 100
[Feishu] Starting WebSocket client for app cli_a9103ecc9fb85bd8...
[Feishu] WebSocket connected successfully        ← 这行应该出现
[Feishu] Connected at 2026-02-23T...
[Feishu MCP] MCP server running on stdio
[Feishu MCP] Ready to receive requests
```

## 📱 添加机器人到飞书

1. 打开飞书客户端（电脑或手机）
2. 在搜索框中输入你的机器人名称
3. 点击 **"添加"** 或 **"添加到群聊"**
4. 发送测试消息：`你好`

## 🤖 配置Claude Desktop

### Windows配置文件位置

```
%APPDATA%\Claude\claude_desktop_config.json
```

完整路径通常是：
```
C:\Users\Admin\AppData\Roaming\Claude\claude_desktop_config.json
```

### 配置内容

```json
{
  "mcpServers": {
    "feishu": {
      "command": "node",
      "args": [
        "C:\\Users\\Admin\\feishu-mcp-server\\dist\\index.js"
      ],
      "env": {
        "FEISHU_APP_ID": "cli_a9103ecc9fb85bd8",
        "FEISHU_APP_SECRET": "qRyCROVPjtZDjCuZqDNIPdeWteHOnVck"
      }
    }
  }
}
```

**注意**:
- Windows路径需要使用双反斜杠 `\\`
- 如果文件不存在，创建该文件

### 完全重启Claude Desktop

1. 完全退出Claude Desktop（确保进程完全关闭）
2. 重新启动Claude Desktop
3. 在对话框中测试MCP工具

## 🧪 测试流程

### 1. 在飞书中发送消息

```
你: 测试消息
```

### 2. 在Claude中对话

```
你: 检查飞书消息
Claude: [调用 feishu_get_messages]
Claude: 收到1条新消息：
     发送者: xxx
     内容: "测试消息"
     时间: 2026-02-23 19:30:00

你: 回复"收到！已连接成功"
Claude: [调用 feishu_send_message]
Claude: ✅ 消息已发送到飞书
```

## ❓ 故障排查

### 问题1: WebSocket连接失败 (404)

**原因**: 飞书应用未启用长连接模式

**解决方案**:
1. 确认在"事件订阅"中选择了"使用长连接接收事件"
2. 确认应用已发布
3. 等待1-2分钟后重试

### 问题2: 权限不足 (99991663)

**原因**: 权限未申请或未通过

**解决方案**:
1. 检查"权限管理"中的权限状态
2. 确保申请了 `im:message` 等必要权限
3. 等待权限审核通过

### 问题3: 应用未发布

**原因**: 应用还在开发状态

**解决方案**:
1. 进入"版本管理与发布"
2. 创建版本并发布到本企业

### 问题4: Claude找不到MCP工具

**原因**: Claude Desktop配置错误

**解决方案**:
1. 检查配置文件路径是否正确
2. 确认JSON格式正确（可以用在线JSON验证器）
3. 完全重启Claude Desktop
4. 查看Claude Desktop的日志

## 📞 需要帮助？

如果遇到问题，请检查：
1. 飞书开放平台的配置是否完整
2. 服务是否成功启动（查看日志）
3. Claude Desktop配置是否正确
4. 飞书客户端是否添加了机器人

---

## 📊 配置检查清单

在启动服务前，请确认：

### 飞书开放平台配置
- [ ] 机器人能力已启用
- [ ] 权限 `im:message` 已添加
- [ ] 权限 `im:message:group_at_msg` 已添加
- [ ] 权限 `im:chat` 已添加
- [ ] 事件订阅选择"使用长连接接收事件"
- [ ] 事件 `im.message.receive_v1` 已添加
- [ ] 应用已发布到本企业

### 本地环境配置
- [x] .env 文件已创建
- [x] App ID 配置正确
- [x] App Secret 配置正确
- [x] 项目已编译（dist目录存在）
- [x] 依赖已安装（node_modules）

### Claude Desktop配置
- [ ] 配置文件已创建/修改
- [ ] 路径配置正确
- [ ] 环境变量配置正确
- [ ] Claude Desktop已重启

---

**完成所有配置后，服务将可以正常工作！** 🎉
