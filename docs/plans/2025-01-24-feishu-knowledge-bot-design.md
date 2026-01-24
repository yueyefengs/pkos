# 飞书个人知识库机器人 - 设计文档

## 概述

通过飞书机器人接收抖音/B站视频链接，自动下载、转录、LLM优化后保存到飞书多维表格，构建个人知识库。

## 需求

- 触发方式：飞书官方机器人
- 支持平台：抖音、B站
- 处理模式：异步处理
- 存储位置：飞书多维表格
- 多LLM支持：OpenAI、DeepSeek、GLM、Claude
- 部署方式：Docker

## 系统架构

```
┌─────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   飞书用户   │ ───> │   飞书服务器     │ ───> │  FastAPI服务    │
└─────────────┘      └─────────────────┘      └────────┬────────┘
                                                     │
                      ┌──────────────┬──────────────┼──────────────┐
                      ▼              ▼              ▼              ▼
              ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
              │ 视频下载器  │ │   转录器    │ │ 内容处理器  │ │   飞书客户端  │
              └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
                      │              │              │
                      ▼              ▼              ▼
              ┌─────────────────────────────────────────────────────┐
              │              PostgreSQL + Redis                      │
              └─────────────────────────────────────────────────────┘
```

## 核心组件

### bot/feishu_client.py
- 封装飞书开放平台API
- 发送消息、读写多维表格
- 事件签名验证

### processors/video_downloader.py
- B站：yt-dlp
- 抖音：Selenium
- 提取音频到临时目录

### processors/transcriber.py
- faster-whisper语音识别
- 语言检测

### processors/content_processor.py
- LLM优化文稿
- 支持多LLM切换
- Prompt模板加载

### processors/llm_client.py
- 统一LLM接口
- OpenAI兼容（OpenAI/DeepSeek/GLM）
- Anthropic SDK（Claude）

### models/task.py
- 任务状态：processing/completed/failed
- 任务数据结构

### storage/postgres.py
- PostgreSQL异步访问
- 任务状态持久化

## 数据流

1. 用户@机器人发送视频链接
2. 飞书推送事件到`/feishu/events`
3. 验证URL，立即回复"收到，正在处理..."
4. 创建任务（status=processing）
5. 异步处理：
   - 下载并提取音频
   - Whisper转录
   - LLM优化文稿
   - 每步发送进度消息
6. 写入多维表格
7. 发送完成通知
8. 更新任务状态为completed

## 数据库表结构

```sql
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(36) UNIQUE NOT NULL,
    video_url TEXT NOT NULL,
    title VARCHAR(500),
    platform VARCHAR(50),
    status VARCHAR(20) DEFAULT 'processing',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT,
    content TEXT
);
```

## 多维表格字段

| 字段 | 类型 | 说明 |
|------|------|------|
| 标题 | 文本 | 视频标题 |
| 来源URL | URL | 视频链接 |
| 处理状态 | 单选 | 处理中/已完成/失败 |
| 创建时间 | 日期 | 创建时间 |
| 文稿内容 | 多行文本 | LLM优化后的内容 |

## 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| URL格式无效 | 立即提示用户 |
| 不支持的平台 | 提示"仅支持抖音/B站" |
| 下载失败 | 通知用户具体原因 |
| 转录失败 | 通知用户 |
| LLM失败 | 保存原始转录，记录错误 |
| 飞书API失败 | 记录日志 |

**策略：失败即通知，不自动重试**

## 配置

### 环境变量

```env
# 飞书应用
FEISHU_APP_ID=cli_xxxx
FEISHU_APP_SECRET=xxxxx
FEISHU_BOT_NAME=知识助手
FEISHU_ENCRYPT_KEY=xxxxx

# 飞书多维表格
FEISHU_BITABLE_TOKEN=xxxxx
FEISHU_BITABLE_TABLE_ID=xxxxx

# 数据库
DB_HOST=db
DB_PORT=5432
DB_USER=feishu
DB_PASSWORD=feishu123
DB_NAME=feishu_knowledge

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# 服务
HOST=0.0.0.0
PORT=8080

# 抖音
DOUYIN_COOKIES_FILE=douyin_cookies.txt

# LLM配置文件路径
LLM_CONFIG_FILE=config/llm_config.json
```

### LLM配置 (config/llm_config.json)

```json
{
  "default": "deepseek",
  "models": {
    "openai": {
      "type": "openai",
      "api_key": "sk-xxxxx",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4o"
    },
    "deepseek": {
      "type": "openai",
      "api_key": "sk-xxxxx",
      "base_url": "https://api.deepseek.com/v1",
      "model": "deepseek-chat"
    },
    "glm": {
      "type": "openai",
      "api_key": "xxxxx",
      "base_url": "https://open.bigmodel.cn/api/paas/v4",
      "model": "glm-4"
    },
    "claude": {
      "type": "claude",
      "api_key": "sk-ant-xxxxx",
      "model": "claude-3-5-sonnet-20241022"
    }
  }
}
```

## 目录结构

```
feishu-knowledge-bot/
├── config/
│   ├── settings.py
│   ├── prompts/
│   └── llm_config.json
├── bot/
│   ├── main.py
│   ├── feishu_client.py
│   └── webhook.py
├── processors/
│   ├── video_downloader.py
│   ├── transcriber.py
│   ├── content_processor.py
│   └── llm_client.py
├── models/
│   └── task.py
├── storage/
│   └── postgres.py
├── temp/
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── .dockerignore
├── requirements.txt
├── .env.example
└── README.md
```

## Docker部署

### 开发模式

```bash
docker-compose -f docker/docker-compose.dev.yml up
```

### 生产模式

```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 常用命令

```bash
# 查看日志
docker-compose -f docker/docker-compose.yml logs -f

# 停止服务
docker-compose -f docker/docker-compose.yml down

# 重新构建
docker-compose -f docker/docker-compose.yml build --no-cache
```

## 飞书开放平台配置

1. 创建企业自建应用
2. 开启机器人能力
3. 配置权限：获取与发送消息、读写多维表格
4. 配置事件订阅：`/feishu/events`
5. 获取App ID、Secret、Encrypt Key

## 依赖

- fastapi + uvicorn
- httpx
- asyncpg
- redis
- faster-whisper
- yt-dlp
- selenium
- openai
- anthropic
- pydantic-settings
