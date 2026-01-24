# 飞书个人知识库机器人

通过飞书机器人接收抖音/B站视频链接，自动下载、转录、LLM优化后保存到飞书多维表格。

## 功能特性

- 支持抖音、B站视频下载
- Whisper语音识别转录
- LLM智能优化文稿
- 多LLM支持：OpenAI、DeepSeek、GLM、Claude
- 自动保存到飞书多维表格
- 异步处理，实时进度反馈

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

### 4. 使用

在飞书中@机器人发送视频链接，机器人会自动处理并保存到多维表格。

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
