# 飞书长链接（WebSocket）模式配置指南

## 概述

PKOS 支持两种飞书事件接收模式：

1. **WebSocket 长链接模式** ✅ **推荐**
   - 无需公网 IP 或域名
   - 无需处理签名验证和解密
   - 配置简单，5分钟完成
   - 自动重连机制

2. **Webhook 模式**（传统方式）
   - 需要公网 IP 或域名
   - 需要处理签名验证和解密
   - 配置复杂，需要配置反向代理

## 快速开始 - WebSocket 长链接模式

### 1. 在飞书开放平台配置

1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 进入你的应用 → **事件订阅**
3. 选择 **"使用长链接接收事件"**
4. 状态会显示为 **"建立连接"** - 这是正常的，等服务启动后会自动连接

### 2. 环境变量配置

在 `.env` 文件中添加或修改：

```bash
# 飞书应用配置
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxx

# 事件接收模式 (websocket 或 webhook)
FEISHU_EVENT_MODE=websocket

# 注意：长链接模式不需要 FEISHU_ENCRYPT_KEY
```

### 3. 启动服务

```bash
# 开发模式
python3 bot/main.py

# 或使用 Docker
docker-compose up -d bot
```

### 4. 验证连接

查看日志，应该看到：

```
📡 Using WebSocket long connection mode for event reception
Starting Feishu WebSocket long connection client...
WebSocket client thread started
✅ WebSocket client connected successfully
```

在飞书开放平台的事件订阅页面，状态会从"建立连接"变为 **"已连接"**。

## 配置对比

| 特性 | WebSocket 长链接 | Webhook |
|------|-----------------|---------|
| 公网 IP/域名 | ❌ 不需要 | ✅ 必需 |
| 签名验证 | ❌ 自动处理 | ✅ 需要实现 |
| 加密解密 | ❌ 自动处理 | ✅ 需要实现 |
| 配置复杂度 | 🟢 简单 | 🔴 复杂 |
| 部署时间 | 5分钟 | 1小时+ |
| 连接数限制 | 每应用50个 | 无限制 |
| 适用场景 | 本地开发、内网部署 | 公网生产环境 |

## 技术细节

### WebSocket 客户端实现

系统使用 `lark_oapi` SDK 的 `ws.Client` 来建立 WebSocket 长链接：

```python
ws_client = lark.ws.Client(
    app_id,
    app_secret,
    event_handler=event_handler,
    log_level=lark.LogLevel.INFO
)
ws_client.start()
```

### 线程模型

WebSocket 客户端在独立的 daemon 线程中运行，不会阻塞 FastAPI 主服务。

**关键技术细节 - 事件循环隔离：**

lark-oapi SDK 的 `ws.Client` 在模块级别获取事件循环，并使用 `loop.run_until_complete()` 启动。这与 FastAPI 的 uvloop 冲突（错误：`this event loop is already running`）。

**解决方案：** 在独立线程中创建新的事件循环：

```python
def start_websocket_client():
    import asyncio

    # 为线程创建独立的事件循环
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)

    # 修补 SDK 模块的事件循环引用
    import lark_oapi.ws.client as ws_client_module
    ws_client_module.loop = new_loop

    # 启动客户端（会阻塞，但在独立线程中运行）
    client = lark.ws.Client(app_id, app_secret, event_handler=event_handler)
    client.start()

# 在 daemon 线程中运行
thread = threading.Thread(target=start_websocket_client, daemon=True)
thread.start()
```

这样每个线程都有自己的事件循环，互不干扰。

### 事件分发器

两种模式共享同一个事件分发器 (`EventDispatcherHandler`)，因此切换模式不需要修改业务逻辑：

```python
event_handler = EventDispatcherHandler.builder(
    "",  # 长链接模式不需要 encrypt_key
    "",  # 长链接模式不需要 verification_token
    lark.LogLevel.INFO
).register_p2_im_message_receive_v1(
    handle_message_receive
).build()
```

## 故障排查

### 1. 事件循环冲突错误 ⚠️

**症状**: `RuntimeError: this event loop is already running`

```
[Lark] [2026-01-26 14:29:03,425] [ERROR] connect failed, err: this event loop is already running.
```

**原因**:
- lark-oapi SDK 尝试在已运行的事件循环中调用 `run_until_complete()`
- FastAPI 的 uvloop 与 SDK 的事件循环冲突

**解决**:
✅ **已修复** - 代码已自动在独立线程中创建新的事件循环。如果仍遇到此错误：
1. 确保使用最新版本的代码
2. 检查是否有其他地方直接调用了 `ws_client.start()`
3. 重启服务

### 2. 连接失败

**症状**: 日志显示 "Failed to start WebSocket client"

**解决**:
- 检查 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 是否正确
- 检查网络连接，确保可以访问 `wss://open.feishu.cn`
- 检查防火墙规则

### 3. 事件订阅显示"建立连接"

**症状**: 飞书开放平台一直显示"建立连接"

**原因**:
- 服务未启动
- WebSocket 客户端初始化失败
- 网络连接问题

**解决**:
1. 启动服务并查看日志
2. 确认看到 "✅ WebSocket client connected successfully"
3. 刷新飞书开放平台页面

### 3. 消息收不到

**症状**: 连接成功但收不到消息

**检查**:
1. 确认已在飞书开放平台订阅了 `im.message.receive_v1` 事件
2. 确认机器人已被添加到群聊
3. 在群聊中 @ 机器人发送消息
4. 查看日志确认事件处理器是否被调用

### 4. 连接断开

**症状**: 运行一段时间后连接断开

**解决**: SDK 会自动重连，无需手动处理。如果频繁断开：
- 检查网络稳定性
- 检查是否超过了50个连接的限制（每个应用最多50个连接）

## 切换回 Webhook 模式

如果需要切换回 Webhook 模式：

1. 修改 `.env`:
```bash
FEISHU_EVENT_MODE=webhook
FEISHU_ENCRYPT_KEY=your_encrypt_key  # 需要设置加密密钥
```

2. 在飞书开放平台配置 Webhook URL:
```
https://your-domain.com/feishu/events
```

3. 重启服务

## 参考资料

- [飞书长链接 Python 开发指南](https://www.zyfun.cn/338.html)
- [飞书 SDK 文档](https://github.com/larksuite/oapi-sdk-python)
- [飞书开放平台事件订阅](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-configure-/request-url-configuration-case)

## 常见问题

**Q: 长链接模式是否适用于生产环境？**

A: 是的，长链接模式稳定可靠，适用于生产环境。唯一的限制是每个应用最多50个连接。

**Q: 如何监控 WebSocket 连接状态？**

A: 可以通过健康检查端点 `/health` 来检查服务状态。未来会添加 WebSocket 连接状态的监控端点。

**Q: 长链接断开后会自动重连吗？**

A: 是的，lark-oapi SDK 内置了自动重连机制。

**Q: 可以同时使用两种模式吗？**

A: 不建议。虽然技术上可以，但会导致重复处理消息。请选择一种模式使用。

**Q: 切换模式需要修改代码吗？**

A: 不需要。只需修改环境变量 `FEISHU_EVENT_MODE` 并重启服务即可。
