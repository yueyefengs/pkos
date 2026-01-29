# Telegram Bot部署指南

## 概述

PKOS Telegram Bot是一个视频学习助手,可以下载并转录视频(抖音/B站),提供智能对话和学习模式指导。

## 特性

### 核心功能
- 📹 **视频处理**: 支持抖音和B站视频的下载、转录和内容优化
- 💬 **智能对话**: 基于LLM的问答系统,支持针对视频内容的多轮对话
- 🎓 **学习模式**: 苏格拉底式教学方法,引导主动思考
- 📊 **进度追踪**: 学习时长、提问次数、概念掌握度统计
- 📝 **内容分析**: 大纲生成、内容总结、Q&A生成、扩展阅读建议

### 工作区模式
- 支持同时管理多篇文章
- 显式激活文章进行对话
- 普通模式(直接问答)和学习模式(引导式教学)切换

## 环境要求

### 基础环境
- Python 3.9+
- PostgreSQL 12+
- Redis 6+

### 系统依赖
```bash
# macOS
brew install ffmpeg postgresql redis

# Ubuntu/Debian
sudo apt install ffmpeg postgresql redis-server
```

### Python依赖
```bash
pip install -r requirements.txt
```

主要依赖:
- `python-telegram-bot[all]==20.8` - Telegram Bot框架
- `redis[hiredis]>=5.0.0` - Redis异步客户端
- `asyncpg` - PostgreSQL异步客户端
- `faster-whisper` - 音频转录
- `yt-dlp` - 视频下载
- `openai` / `anthropic` - LLM API客户端

## 配置

### 1. 创建Telegram Bot

1. 在Telegram中找到 [@BotFather](https://t.me/botfather)
2. 发送 `/newbot` 创建新bot
3. 按提示设置bot名称和用户名
4. 获取Bot Token (格式: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### 2. 环境变量配置

复制`.env.example`到`.env`,填写必要配置:

```bash
# Telegram Bot配置
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=your_bot_username

# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_USER=feishu
DB_PASSWORD=feishu123
DB_NAME=feishu_knowledge

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# LLM配置(至少配置一个)
LLM_DEFAULT_PROVIDER=openai  # 或 deepseek / glm / claude

# OpenAI配置
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o

# Claude配置(可选)
CLAUDE_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-3-5-sonnet-20241022
```

### 3. 数据库初始化

```bash
# 创建数据库
createdb feishu_knowledge

# 表结构会在首次启动时自动创建
```

## 启动

### 方式一:直接启动

```bash
python3 start_telegram_bot.py
```

### 方式二:后台运行

```bash
# 使用nohup
nohup python3 start_telegram_bot.py > telegram_bot.log 2>&1 &

# 使用systemd (推荐)
sudo cp deploy/telegram-bot.service /etc/systemd/system/
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

### 方式三:Docker部署

```bash
# 构建镜像
docker build -t pkos-telegram-bot .

# 运行容器
docker run -d \
  --name pkos-telegram-bot \
  --env-file .env \
  -v $(pwd)/douyin_cookies.txt:/app/douyin_cookies.txt \
  pkos-telegram-bot
```

## 使用指南

### 基础命令

```
/start - 开始使用
/help - 查看帮助
/history - 查看最近处理的视频
```

### 工作区管理

```
/chat [任务ID] - 激活文章并进入普通对话模式
/learn [任务ID] - 激活文章并进入学习模式
/add [任务ID] - 添加文章到工作区
/context - 查看当前工作区内容
/clear - 清空工作区
```

### 模式切换

```
/mode normal - 切换到普通对话模式
/mode learning - 切换到学习模式
```

### 内容分析

```
/outline - 生成内容大纲
/summary - 生成内容总结
/qa - 生成常见问题解答
/extend - 生成扩展阅读建议
```

### 进度追踪

```
/progress - 查看当前文章学习进度
/workspace - 查看工作区所有进度
/stats - 查看学习统计
/checkpoint - 保存学习检查点
```

### 使用流程

1. **发送视频链接**
   ```
   发送: https://www.douyin.com/video/xxxxx
   Bot会自动处理并返回任务ID
   ```

2. **激活文章进行对话**
   ```
   /chat 123  (普通模式)
   或
   /learn 123  (学习模式)
   ```

3. **开始提问**
   ```
   直接发送问题:
   "这个视频的核心观点是什么?"
   ```

4. **使用分析功能**
   ```
   /outline  - 查看结构化大纲
   /summary  - 查看精炼总结
   /qa       - 查看常见问答
   ```

## 架构说明

### 模块结构

```
bot/
├── telegram_client.py      # Telegram API封装
├── session_manager.py      # Redis会话管理
├── command_handlers.py     # 命令处理器
├── message_handler.py      # 消息路由和URL检测
├── conversation_engine.py  # LLM对话引擎
├── content_analysis.py     # 内容分析功能
├── progress_tracker.py     # 学习进度追踪
└── telegram_main.py        # 主程序入口

storage/
└── postgres.py             # 数据库存储层(扩展了学习进度表)

models/
└── task.py                 # 数据模型(添加了学习进度模型)

processors/
├── video_downloader.py     # 视频下载器
├── transcriber.py          # 音频转录器
├── content_processor.py    # 内容处理器
└── llm_client.py           # LLM客户端(扩展了对话方法)
```

### 数据流

```
用户消息 → MessageHandler
           ↓
    检测URL?
    ├─ 是 → VideoProcessor → 下载 → 转录 → 优化 → 保存
    └─ 否 → ConversationEngine → LLM → 回复用户
```

### 数据库表

```sql
-- 任务表(已有)
tasks (id, task_id, video_url, title, platform, status, content, ...)

-- 学习进度表(新增)
learning_progress (id, user_id, task_id, status, study_time, questions_asked, ...)

-- 概念掌握表(新增)
concept_mastery (id, progress_id, concept, status, notes, ...)

-- 学习检查点表(新增)
learning_checkpoints (id, progress_id, content, position, ...)
```

### Redis键结构

```
workspace:{user_id}          - 工作区任务ID列表
mode:{user_id}               - 对话模式(normal/learning)
history:{user_id}            - 对话历史(最近50条)
study_time:{user_id}:{task_id} - 学习会话开始时间
```

## 监控与日志

### 日志位置
- 标准输出: `telegram_bot.log`
- 错误日志: 同上(stderr重定向)

### 日志级别
在`config/logger.py`中调整:
```python
logging.basicConfig(level=logging.INFO)  # 或 DEBUG
```

### 健康检查
```bash
# 检查进程
ps aux | grep telegram_bot

# 检查Redis连接
redis-cli ping

# 检查PostgreSQL连接
psql -U feishu -d feishu_knowledge -c "SELECT count(*) FROM tasks;"
```

## 常见问题

### 1. Bot无法响应
- 检查Token是否正确
- 确认网络可以访问Telegram API
- 查看日志获取错误信息

### 2. 视频下载失败
- 确认`ffmpeg`已安装
- 抖音视频需要cookies文件(`douyin_cookies.txt`)
- B站视频可能需要登录cookies

### 3. Redis连接失败
- 确认Redis服务运行: `redis-cli ping`
- 检查Redis配置(host/port/db)

### 4. 数据库连接失败
- 确认PostgreSQL服务运行
- 检查数据库配置(user/password/database)
- 确认数据库已创建

### 5. LLM API调用失败
- 检查API Key是否有效
- 确认API额度充足
- 验证网络可以访问API端点

## 安全建议

1. **Token保护**: 不要将`.env`文件提交到git仓库
2. **权限控制**: 考虑添加用户白名单机制
3. **API限流**: 对LLM调用实施速率限制
4. **数据备份**: 定期备份PostgreSQL数据库
5. **日志脱敏**: 确保日志不包含敏感信息

## 性能优化

1. **Redis缓存**: 对话历史和工作区状态已使用Redis
2. **异步处理**: 视频处理使用异步任务,不阻塞用户交互
3. **连接池**: PostgreSQL使用asyncpg连接池
4. **消息分割**: 长消息自动分段发送,避免超限

## 升级说明

### 从Feishu迁移到Telegram

原有的Feishu功能保持不变,Telegram bot是新增的独立模块:

- 共用数据库和存储层
- 共用视频处理流程
- 共用LLM配置
- 学习进度功能仅Telegram bot支持

可以同时运行Feishu bot和Telegram bot。

## 贡献

欢迎提交Issue和Pull Request!

## 许可

MIT License
