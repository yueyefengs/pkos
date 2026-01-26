# 飞书官方SDK迁移设计方案

**日期**: 2026-01-26
**作者**: Claude Sonnet 4.5
**状态**: 已验证

## 概述

将PKOS项目的飞书集成从手动httpx调用迁移到官方lark-oapi SDK，实现代码简化、类型安全和自动化token管理。

## 背景

### 当前架构问题

1. **Token管理繁琐** - 手动管理 `tenant_access_token` 生命周期
2. **签名验证自实现** - `verify_event()` 方法自己处理HMAC签名
3. **缺乏类型系统** - API参数使用裸字典，容易出错
4. **事件处理耦合** - webhook直接解析JSON，缺少分发机制
5. **维护成本高** - API更新需手动同步

### 目标架构

采用 **lark-oapi** 官方Python SDK:
- 自动Token管理
- 内置签名验证
- 完整类型系统
- 语义化API接口
- 事件分发器自动路由

## 核心架构变更

### 1. Client初始化改造

**原有方式**:
```python
class FeishuClient:
    def __init__(self):
        self.app_id = settings.feishu_app_id
        self.app_secret = settings.feishu_app_secret
        self.tenant_access_token = None  # 手动管理
        self.base_url = "https://open.feishu.cn/open-apis"
```

**SDK方式**:
```python
import lark_oapi as lark

class FeishuClient:
    def __init__(self):
        self.client = lark.Client.builder() \
            .app_id(settings.feishu_app_id) \
            .app_secret(settings.feishu_app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()
```

**优势**:
- SDK自动管理token，删除 `get_tenant_access_token()` 方法
- 删除 `verify_event()` 方法
- 移除所有httpx依赖代码

### 2. 发送消息改造

**原有方式** (手动拼接):
```python
async def send_message(self, receive_id: str, msg_type: str, content: str):
    token = await self.get_tenant_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{self.base_url}/im/v1/messages?receive_id_type=open_id",
            headers={"Authorization": f"Bearer {token}"},
            json={"receive_id": receive_id, ...}
        )
```

**SDK方式** (类型安全):
```python
def send_message(self, receive_id: str, msg_type: str = "text", content: str = ""):
    from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

    request = CreateMessageRequest.builder() \
        .receive_id_type("open_id") \
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(receive_id)
            .msg_type(msg_type)
            .content(json.dumps({"text": content}))
            .build()
        ).build()

    response = self.client.im.v1.message.create(request)

    if not response.success():
        logger.error(f"发送消息失败: {response.code} - {response.msg}")
        raise Exception(f"发送消息失败: {response.msg}")

    return response.data
```

**改进**:
- 类型安全 - `CreateMessageRequest` 而非裸字典
- 自动错误检查 - `response.success()`
- 无需管理token
- 同步调用简化复杂度

### 3. 多维表格操作改造

**原有方式**:
```python
async def create_record(self, title: str, video_url: str, content: str) -> str:
    token = await self.get_tenant_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{self.base_url}/bitable/v1/apps/{self.bitable_token}/tables/{self.bitable_table_id}/records",
            headers={"Authorization": f"Bearer {token}"},
            json={"fields": {"标题": title, ...}}
        )
```

**SDK方式**:
```python
def create_record(self, title: str, video_url: str, content: str) -> str:
    from lark_oapi.api.bitable.v1 import (
        CreateAppTableRecordRequest,
        CreateAppTableRecordRequestBody
    )

    request = CreateAppTableRecordRequest.builder() \
        .app_token(settings.feishu_bitable_token) \
        .table_id(settings.feishu_bitable_table_id) \
        .request_body(
            CreateAppTableRecordRequestBody.builder()
            .fields({
                "标题": title,
                "来源URL": video_url,
                "处理状态": "已完成",
                "文稿内容": content
            })
            .build()
        ).build()

    response = self.client.bitable.v1.app_table_record.create(request)

    if not response.success():
        raise Exception(f"创建记录失败: {response.msg}")

    return response.data.record.record_id
```

### 4. 事件处理机制改造

**架构对比**:

原有架构:
```
FastAPI POST /feishu/events
  → 手动解析JSON event.get("type")
  → if event_type == "message.receive_v1":
      → webhook_handler.handle_message()
```

新架构:
```
FastAPI POST /feishu/events
  → EventDispatcherHandler.do(request)
  → SDK自动路由到注册的处理函数
  → def handle_message_receive(data: P2ImMessageReceiveV1)
```

**实现**:

```python
# bot/main.py
from lark_oapi import EventDispatcherHandler, LogLevel
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

event_handler = EventDispatcherHandler.builder(
    settings.feishu_encrypt_key or "",
    "",  # verification_token可选
    LogLevel.INFO
).register_p2_im_message_receive_v1(
    lambda data: webhook_handler.handle_message_receive(data)
).build()
```

### 5. WebhookHandler事件处理重写

**原有方式** (手动解析):
```python
async def handle_message(self, event: Dict[str, Any]) -> Dict[str, Any]:
    chat_type = event.get("chat_type", "")
    content = event.get("content", {})
    sender_id = event.get("sender", {}).get("sender_id", {}).get("open_id", "")
    text = content.get("text", "")
```

**SDK方式** (强类型):
```python
def handle_message_receive(self, data: P2ImMessageReceiveV1) -> None:
    """处理飞书消息事件 - SDK自动解析"""
    event = data.event
    message = event.message
    sender = event.sender

    # 群聊@检测
    if message.chat_type == "group":
        mentions = message.mentions
        if not mentions or not any(m.id.user_id == settings.feishu_app_id for m in mentions):
            return

    # 提取消息内容
    text = json.loads(message.content).get("text", "")
    sender_id = sender.sender_id.open_id

    # 提取视频URL
    video_url = self._extract_video_url(text)
    if not video_url:
        feishu_client.send_message(sender_id, content="请发送有效的抖音或B站视频链接")
        return

    # 异步处理视频
    asyncio.create_task(self._process_video(task_id, video_url, sender_id))
```

**改进**:
- `P2ImMessageReceiveV1` 提供完整消息结构
- 不再需要层层 `.get()` 防止KeyError
- IDE自动补全字段
- `mentions` 字段直接可用

### 6. 异步/同步混合处理

**解决方案**: SDK同步调用 + FastAPI异步框架

```python
# feishu_client 使用同步方法
def send_message(self, receive_id: str, content: str):
    response = self.client.im.v1.message.create(request)
    return response.data

# webhook_handler 中异步调用同步方法
async def _process_video(self, task_id: str, video_url: str, user_id: str):
    # FastAPI自动处理线程池调度
    feishu_client.send_message(user_id, content="正在下载视频...")

    # 其他异步操作保持不变
    audio_path, title = await video_downloader.download(video_url)

    # 调用同步SDK
    record_id = feishu_client.create_record(title, video_url, processed_content)
```

**说明**: FastAPI可在异步端点中调用同步函数，框架自动处理。

### 7. FastAPI事件端点改造

**原有方式**:
```python
@app.post("/feishu/events")
async def handle_feishu_event(request: Request):
    body = await request.body()
    data = await request.json()

    # URL验证
    if "url_verify" in data:
        return PlainTextResponse(content=data.get("challenge", ""))

    # 签名验证
    if not feishu_client.verify_event(timestamp, nonce, body.decode(), signature):
        raise HTTPException(status_code=403)

    # 手动路由
    if event_type == "message.receive_v1":
        result = await webhook_handler.handle_message(event)
```

**SDK方式**:
```python
from lark_oapi.adapter.fastapi import parse_req, parse_resp

@app.post("/feishu/events")
def handle_feishu_event(request: Request):
    """处理飞书事件 - SDK自动验证签名和路由"""
    lark_request = parse_req(request)
    response = event_handler.do(lark_request)
    return parse_resp(response)
```

**关键点**:
- `EventDispatcherHandler.do()` 自动处理URL验证和签名
- 不再手动解析body和headers
- 端点从 `async def` 改为 `def`
- 使用SDK提供的 `parse_req/parse_resp` 适配器

## 依赖更新

**requirements.txt**:
```diff
  fastapi
  uvicorn[standard]
- httpx
+ lark-oapi
  asyncpg
  redis
  faster-whisper
  yt-dlp
  openai
  anthropic
  pydantic-settings
  python-dotenv
```

## 迁移步骤

1. **安装SDK并验证** - `pip install lark-oapi`，测试基本连接
2. **重构FeishuClient** - 替换httpx为SDK，保持方法签名
3. **改造WebhookHandler** - 重写事件处理函数
4. **集成EventDispatcher** - 修改main.py事件端点
5. **移除遗留代码** - 删除httpx依赖和手动验证逻辑
6. **测试验证** - 测试消息、多维表格、完整视频处理流程

## 文件变更清单

- ✏️ `requirements.txt` - httpx → lark-oapi
- ✏️ `bot/feishu_client.py` - 完全重写（减少约40%代码）
- ✏️ `bot/webhook.py` - 重写handle_message方法
- ✏️ `bot/main.py` - 集成EventDispatcherHandler
- ❌ 删除 `feishu_client.verify_event()` 方法
- ❌ 删除 `feishu_client.get_tenant_access_token()` 方法

## 风险与回退

**潜在风险**:
- SDK同步调用可能影响性能（实际影响很小，网络IO占主导）
- SDK版本更新可能破坏兼容性（建议锁定版本号）

**回退策略**:
- 使用git worktree创建隔离分支
- 保留原feishu_client.py为feishu_client_legacy.py备份
- 分阶段测试：本地 → Docker开发环境 → 生产环境

## 预期收益

- ✅ 减少40%飞书相关代码量
- ✅ 完整类型系统，IDE友好
- ✅ SDK自动维护token和签名验证
- ✅ 语义化API调用，易于维护
- ✅ 官方维护，API变更自动同步

## 工作量评估

- 🔧 3个文件重构（feishu_client.py, webhook.py, main.py）
- 📦 1个依赖更新（requirements.txt）
- ✅ 测试验证（消息、多维表格、完整流程）
- ⏱️ 预计2-3小时完成核心重构

## 参考资料

- [lark-oapi GitHub](https://github.com/larksuite/oapi-sdk-python)
- [Flask事件处理示例](https://github.com/larksuite/oapi-sdk-python/blob/v2_main/samples/event/flask_sample.py)
- [lark-oapi PyPI](https://pypi.org/project/lark-oapi/)
- [飞书开放平台文档](https://open.feishu.cn/document/server-docs/server-side-sdk)
