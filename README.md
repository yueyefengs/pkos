# PKOS - 个人知识组织系统

将碎片化的视频信息转化为可复用的个人知识。通过Telegram Bot提供智能对话和学习助手功能。

## 功能特性

### 核心功能
- 📹 支持抖音、B站视频下载和转录
- 🎤 Whisper语音识别转录
- 🤖 LLM智能优化文稿
- 💬 多轮对话问答系统
- 🎓 学习模式(苏格拉底式教学)
- 📊 学习进度追踪
- 📝 内容分析(大纲/总结/Q&A/扩展阅读)

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
- Telegram Bot Token
- LLM API密钥
- 数据库配置
- **代理配置（中国大陆必需）**：
  ```bash
  HTTP_PROXY=http://127.0.0.1:7897
  HTTPS_PROXY=http://127.0.0.1:7897
  ```

### 2. 启动服务

**方式一：使用Docker（推荐）**

⚠️ **代理注意事项**：
- macOS/Windows用户：Docker自动使用`host.docker.internal`访问宿主机代理
- Linux用户：如果代理连接失败，需要在docker-compose.yml中添加：
  ```yaml
  extra_hosts:
    - "host.docker.internal:host-gateway"
  ```

开发模式：
```bash
docker-compose -f docker/docker-compose.dev.yml up
```

生产模式：
```bash
docker-compose -f docker/docker-compose.yml up -d
```

**方式二：本地运行**

```bash
# 1. 确保Redis和PostgreSQL已运行
redis-server &
# PostgreSQL应已在运行

# 2. 启动Telegram Bot
python3 start_telegram_bot.py
```

### 3. 配置抖音Cookies

抖音视频下载需要有效的cookies文件。详细配置请查看: [docs/douyin-cookies-setup.md](docs/douyin-cookies-setup.md)

快速配置:
1. 安装浏览器扩展 "Get cookies.txt LOCALLY"
2. 登录 www.douyin.com
3. 导出cookies并保存为 `douyin_cookies.txt`

### 4. 使用Telegram Bot

详细配置和使用说明请查看: [docs/telegram-bot-setup.md](docs/telegram-bot-setup.md)

基本使用:
1. 在Telegram搜索并启动你的Bot
2. 发送视频链接进行处理
3. 使用`/chat [任务ID]`激活对话模式
4. 使用`/learn [任务ID]`激活学习模式
5. 直接提问或使用`/help`查看所有命令

## 目录结构

```
pkos/
├── bot/              # Telegram机器人模块
├── processors/       # 视频处理模块
├── models/           # 数据模型
├── storage/          # 数据库存储
├── config/           # 配置文件
├── docker/           # Docker配置
└── docs/             # 文档
```

## License

MIT
