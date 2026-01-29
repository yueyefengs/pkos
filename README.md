# PKOS - 个人知识组织系统

将碎片化的视频信息转化为可复用的个人知识。支持飞书和Telegram两种接入方式。

## 功能特性

### 核心功能
- 📹 支持抖音、B站视频下载和转录
- 🎤 Whisper语音识别转录
- 🤖 LLM智能优化文稿
- 💬 多轮对话问答系统
- 🎓 学习模式(苏格拉底式教学)
- 📊 学习进度追踪
- 📝 内容分析(大纲/总结/Q&A/扩展阅读)

### 平台支持
- **飞书Bot**: 自动保存到飞书多维表格
- **Telegram Bot**: 智能对话和学习助手(新)

### 技术特性
- 多LLM支持：OpenAI、DeepSeek、GLM、Claude
- 异步处理，实时进度反馈
- Redis会话管理,PostgreSQL持久化存储

## 快速开始

### 1. 配置环境变量

复制 `.env.example` 到 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置以下信息：
- 飞书应用ID和密钥
- 飞书多维表格token和table_id
- LLM API密钥

### 2. 配置飞书应用

1. 在飞书开放平台创建自建应用
2. 开启机器人能力，获取权限：获取与发送消息、读写多维表格
3. 配置事件订阅：`/feishu/events`

### 3. 启动服务

开发模式：

```bash
docker-compose -f docker/docker-compose.dev.yml up
```

生产模式：

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 4. Telegram Bot部署

详细配置请查看: [docs/telegram-bot-setup.md](docs/telegram-bot-setup.md)

快速启动:
```bash
# 1. 配置Telegram Bot Token
# 编辑 .env 文件,添加:
TELEGRAM_BOT_TOKEN=your_bot_token_here

# 2. 确保Redis和PostgreSQL已运行
redis-server &
# PostgreSQL应已在运行

# 3. 启动Telegram Bot
python3 start_telegram_bot.py
```

### 5. 使用

**飞书Bot**: 在飞书中@机器人发送视频链接，机器人会自动处理并保存到多维表格。

**Telegram Bot**:
1. 发送视频链接进行处理
2. 使用`/chat [任务ID]`激活对话
3. 直接提问或使用`/help`查看所有命令

详细使用说明: [docs/telegram-bot-setup.md](docs/telegram-bot-setup.md)

## 目录结构

```
feishu-knowledge-bot/
├── bot/              # 飞书机器人模块
├── processors/       # 视频处理模块
├── models/           # 数据模型
├── storage/          # 数据库存储
├── config/           # 配置文件
├── docker/           # Docker配置
└── temp/             # 临时文件
```

## License

MIT
