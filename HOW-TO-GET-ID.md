# 如何获取飞书 Open ID

## 方法1: 通过飞书个人主页（推荐）

1. **打开飞书客户端**
2. **点击你的头像** → 进入个人主页
3. **查看浏览器地址栏**（如果是网页版）或分享链接
   - URL格式类似：`https://open.feishu.cn/contact/card/xxxxxxxxxxxx`
   - 或者：`https://example.feishu.cn/personal/xxxxxxxxxxxx`
4. **提取ID部分**（xxxxxxxxxxxx）
5. **添加前缀** `ou_` 变成 `ou_xxxxxxxxxxxxx`

## 方法2: 通过群聊

1. **将机器人添加到任意群聊**
2. **在群里@机器人并发送消息**：`测试`
3. **查看服务日志**：
   ```bash
   tail -f /tmp/feishu-mcp.log
   ```
4. **从日志中获取你的open_id**

## 方法3: 通过飞书开放平台

1. **访问**：https://open.feishu.cn/app/cli_a9103ecc9fb85bd8
2. **进入**：权限管理 → 通讯录
3. **查看用户列表**，可以找到用户ID

## 方法4: 使用脚本快速获取

创建一个文件 `get-openid.js`：

```javascript
const axios = require('axios');

async function getOpenId() {
  // 从飞书获取你的open_id
  // 需要先在飞书中给机器人发送一条消息
}

getOpenId();
```

## Open ID 格式

- **个人用户**: `ou_xxxxxxxxxxxxx`（17位字符）
- **群组**: `oc_xxxxxxxxxxxxx`（17位字符）
- **服务号**: `os_xxxxxxxxxxxxx`（17位字符）

---

## 🎯 快速测试

如果你已经知道自己的open_id，运行：

```bash
node test-send.mjs ou_你的ID "测试消息"
```

或者提供你的open_id，我帮你发送测试消息！
