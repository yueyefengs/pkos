# 飞书机器人功能测试指南

## 测试前准备

### 1. 确认配置

检查 `.env` 文件包含必要配置：

```bash
# 查看当前配置（不显示敏感信息）
cat .env | grep FEISHU | grep -v SECRET | grep -v KEY
```

应该看到：
```
FEISHU_APP_ID=cli_xxxxxxxxxx
FEISHU_BOT_NAME=知识助手
FEISHU_EVENT_MODE=websocket
FEISHU_BITABLE_TOKEN=xxxxx
FEISHU_BITABLE_TABLE_ID=xxxxx
```

### 2. 确认飞书开放平台配置

登录 [飞书开放平台](https://open.feishu.cn/)，确认：

✅ **事件订阅** → 已选择 "使用长链接接收事件"
✅ **权限管理** → 已开通以下权限：
- `im:message` - 获取与发送单聊、群组消息
- `im:message.group_at_msg` - 接收群聊中@机器人消息事件
- `im:message.p2p_msg` - 接收单聊消息事件
- `bitable:app` - 查看、编辑和管理多维表格

✅ **机器人** → 已启用机器人功能

## 测试步骤

### 步骤 1: 启动服务

```bash
# 方式 1: 直接运行（推荐用于调试）
python3 bot/main.py

# 方式 2: 使用 Docker
docker-compose up -d bot
docker-compose logs -f bot
```

### 步骤 2: 验证 WebSocket 连接

启动后，查看日志应该包含：

```
✅ 成功标志：
📡 Using WebSocket long connection mode for event reception
Starting Feishu WebSocket long connection client...
Creating new event loop for WebSocket thread...
WebSocket client initialized, connecting...
✅ WebSocket client connected successfully

❌ 如果出现错误：
- "Failed to start WebSocket client" → 检查 APP_ID 和 APP_SECRET
- "event loop already running" → 代码已修复，不应出现
- 连接超时 → 检查网络，确保能访问 open.feishu.cn
```

### 步骤 3: 确认飞书平台显示连接状态

1. 打开飞书开放平台
2. 进入你的应用 → **事件订阅**
3. 状态应显示为 **"已连接"** 🟢

如果显示 "建立连接"：
- 等待 10-30 秒让连接建立
- 刷新页面
- 检查服务日志是否有错误

### 步骤 4: 添加机器人到测试群

1. 在飞书中创建一个测试群（或使用现有群）
2. 点击群设置 → 群机器人 → 添加机器人
3. 搜索并添加你的机器人（使用 `FEISHU_BOT_NAME` 配置的名称）

### 步骤 5: 发送测试消息

#### 测试 1: 简单文本消息

在群聊中 @ 机器人发送：

```
@知识助手 你好
```

**预期结果：**
- 机器人回复提示消息（例如："请发送有效的抖音或B站视频链接"）
- 服务日志显示收到消息事件

**日志示例：**
```
INFO - Message received from user: xxx
INFO - Content: 你好
INFO - No video URL found in message
```

#### 测试 2: 发送 B站视频链接

在群聊中 @ 机器人发送 B站视频链接：

```
@知识助手 https://www.bilibili.com/video/BV1xx411c7mD
```

**预期结果：**
1. 机器人回复："✅ 收到视频链接，开始处理..."
2. 机器人回复："⏬ 正在下载视频..."
3. 机器人回复："🎤 正在转录音频..."
4. 机器人回复："✨ 正在生成文稿..."
5. 机器人回复："📊 正在保存到多维表格..."
6. 最终回复："✅ 处理完成！已保存到多维表格，记录ID: xxx"

**日志示例：**
```
INFO - Video URL detected: https://www.bilibili.com/video/BV1xx411c7mD
INFO - Task created: task_abc123
INFO - Downloading video...
INFO - Transcribing audio...
INFO - Generating summary...
INFO - Creating bitable record...
INFO - ✅ Processing complete, record ID: recxxxxx
```

#### 测试 3: 发送抖音视频链接

```
@知识助手 https://v.douyin.com/xxxxxx/
```

或复制抖音分享的完整文本（包含链接）。

**预期结果：** 同测试 2

### 步骤 6: 验证多维表格

1. 打开飞书，找到配置的多维表格
2. 检查是否创建了新记录
3. 验证记录包含：
   - 标题
   - 来源 URL
   - 处理状态："已完成"
   - 文稿内容（完整转录）

### 步骤 7: 检查日志文件

```bash
# 查看最新日志
tail -f log/pkos.log

# 搜索特定任务
grep "task_abc123" log/pkos.log

# 查看错误日志
grep ERROR log/pkos.log
```

## 常见问题排查

### 问题 1: 机器人不回复

**可能原因：**

1. **机器人未被 @ 到**
   - 解决：确保在群聊中明确 @ 机器人
   - 验证：日志应显示 "Message received"

2. **权限不足**
   - 解决：检查飞书开放平台的权限配置
   - 验证：查看日志是否有 "permission denied" 错误

3. **事件处理器错误**
   - 解决：查看日志中的 traceback
   - 验证：检查 `webhook_handler.handle_message_receive` 是否被调用

### 问题 2: 视频下载失败

**可能原因：**

1. **视频 URL 无效**
   - 解决：使用有效的 B站/抖音链接
   - 测试：手动访问链接确认视频存在

2. **yt-dlp 过时**
   - 解决：更新 yt-dlp
   ```bash
   pip install --upgrade yt-dlp
   ```

3. **抖音需要 cookies**
   - 解决：参考 CLAUDE.md 中的 Cookie 配置说明

### 问题 3: 转录失败

**可能原因：**

1. **ffmpeg 未安装**
   - 解决：
   ```bash
   # macOS
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt install ffmpeg
   ```

2. **Whisper 模型未下载**
   - 解决：首次运行会自动下载，需要等待
   - 验证：查看日志 "Downloading model..."

### 问题 4: AI 总结失败

**可能原因：**

1. **OpenAI API Key 未配置或无效**
   - 解决：检查 `.env` 中的 `OPENAI_API_KEY`
   - 测试：
   ```bash
   curl https://api.openai.com/v1/models \
     -H "Authorization: Bearer $OPENAI_API_KEY"
   ```

2. **API 配额不足**
   - 解决：检查 OpenAI 账户余额
   - 替代：配置 DeepSeek 或其他兼容 API

### 问题 5: 多维表格写入失败

**可能原因：**

1. **Bitable Token/Table ID 错误**
   - 解决：重新获取并配置
   - 获取方式：打开多维表格 URL，格式为：
     ```
     https://xxx.feishu.cn/base/[BITABLE_TOKEN]?table=[TABLE_ID]
     ```

2. **权限不足**
   - 解决：在飞书开放平台添加 `bitable:app` 权限

## 性能测试

### 测试短视频（< 5分钟）

```bash
# 预期处理时间：2-5分钟
# - 下载：30秒 - 1分钟
# - 转录：1-2分钟
# - AI处理：30秒 - 1分钟
```

### 测试长视频（30-60分钟）

```bash
# 预期处理时间：10-20分钟
# - 下载：2-5分钟
# - 转录：5-10分钟
# - AI处理：2-3分钟
```

**注意：** 长视频建议使用 Whisper `base` 或 `small` 模型，`large` 模型会很慢。

## 自动化测试

### 单元测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_feishu_client.py -v
pytest tests/test_feishu_event_handler.py -v

# 查看测试覆盖率
pytest --cov=bot --cov-report=html
```

### 集成测试（需要真实凭证）

```bash
# 测试飞书客户端初始化
python3 -c "from bot.feishu_client import feishu_client; print('✅ Client initialized')"

# 测试发送消息（需要真实 open_id）
python3 -c "
from bot.feishu_client import feishu_client
feishu_client.send_message('ou_xxxxxx', content='测试消息')
print('✅ Message sent')
"
```

## 监控和日志

### 实时监控

```bash
# 监控服务日志
tail -f log/pkos.log | grep -E "(ERROR|WARN|task_)"

# 监控 Docker 容器
docker-compose logs -f --tail=100 bot

# 监控系统资源
htop  # 或 top
```

### 日志级别

如需更详细的调试信息，修改 `config/logger.py`:

```python
# 开发环境：DEBUG
logger.setLevel(logging.DEBUG)

# 生产环境：INFO
logger.setLevel(logging.INFO)
```

## 下一步

测试通过后，可以：

1. **部署到生产环境**
   ```bash
   docker-compose up -d
   ```

2. **配置多个机器人** - 复制配置，使用不同的 APP_ID

3. **添加更多功能** - 参考 `bot/webhook.py` 扩展消息处理逻辑

4. **优化性能** - 调整 Whisper 模型大小，配置并发处理

5. **监控告警** - 集成日志分析工具（ELK、Grafana 等）

## 获取帮助

- **文档**：`CLAUDE.md`、`docs/feishu-websocket-setup.md`
- **日志**：`log/pkos.log`
- **飞书开放平台文档**：https://open.feishu.cn/document/
- **项目 Issues**：提交 GitHub Issue
