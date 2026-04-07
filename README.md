# PKOS - 个人知识组织系统

将碎片化的视频信息转化为可复用的个人知识。通过 Telegram Bot 提供智能对话和学习助手功能，同时提供 MCP Server 供 AI 客户端调用。

## 功能特性

### 核心功能
- 📹 支持抖音、B站、YouTube 视频下载和转录
- 🎤 Whisper 语音识别转录（本地模型，离线运行）
- 🤖 LLM 智能优化文稿
- 💬 多轮对话问答系统
- 🎓 学习模式（苏格拉底式教学）
- 📊 学习进度追踪
- 📝 内容分析（大纲/总结/Q&A/扩展阅读）
- 🔍 知识库查询与摄入（wiki_query / wiki_ingest）

### 技术特性
- 多 LLM 支持：OpenAI、DeepSeek、GLM、Claude
- 异步处理，实时进度反馈（下载/转录/LLM 三阶段原地编辑同一条消息）
- Redis 会话管理，PostgreSQL 持久化存储
- MCP Server（端口 9000），供 Claude Code / OpenClaw 等 AI 客户端调用

## 快速开始

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，配置以下信息：

| 变量 | 说明 |
|------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API Token |
| `OPENAI_API_KEY` | LLM API 密钥 |
| `OPENAI_BASE_URL` | 自定义 API 端点（选填，默认 OpenAI 官方） |
| `HTTP_PROXY` / `HTTPS_PROXY` | 代理地址（中国大陆必需，如 `http://127.0.0.1:7897`） |

### 2. 准备 Whisper 模型

模型存储在本地 `models/whisper-base/` 目录，Docker 挂载后直接使用，无需运行时联网。

```bash
# 一次性下载（需要联网），之后离线运行
python3 -c "
from faster_whisper import WhisperModel
import shutil, pathlib
m = WhisperModel('base', device='cpu', compute_type='int8')
# 模型缓存在 ~/.cache/huggingface/，手动 cp -L 到 models/whisper-base/
"
```

或直接从已有缓存复制（`-L` 解引用符号链接）：

```bash
cp -L ~/.cache/huggingface/hub/models--Systran--faster-whisper-base/snapshots/<hash>/* models/whisper-base/
```

### 3. 启动服务

**Docker 开发模式（推荐，本地代码实时生效）**

```bash
docker-compose -f docker/docker-compose.dev.yml up --build
```

> macOS/Windows：容器通过 `host.docker.internal` 自动访问宿主机代理。
> Linux：需确保 docker-compose.yml 中含 `extra_hosts: ["host.docker.internal:host-gateway"]`。

**本地运行**

```bash
# 确保 Redis 和 PostgreSQL 已启动
python3 start_telegram_bot.py       # Telegram Bot
python3 mcp_server.py               # MCP Server（端口 9000）
```

### 4. 配置抖音 Cookies

抖音视频下载需要有效的 cookies 文件，详见 [docs/douyin-cookies-setup.md](docs/douyin-cookies-setup.md)。

1. 安装浏览器扩展 "Get cookies.txt LOCALLY"
2. 登录 www.douyin.com
3. 导出 cookies 保存为 `douyin_cookies.txt`（约 30 天有效）

### 5. 使用 Telegram Bot

详见 [docs/telegram-bot-setup.md](docs/telegram-bot-setup.md)。

基本使用：
1. 搜索并启动你的 Bot
2. 发送视频链接（抖音 / B 站 / YouTube）开始处理
3. 处理期间原地更新进度：下载 → 转录 → LLM 优化
4. 处理完成后使用 `/chat [任务ID]` 激活对话模式
5. 使用 `/learn [任务ID]` 激活学习模式
6. 使用 `/help` 查看所有命令

## MCP Server

PKOS 内置 MCP Server，可供 Claude Code、OpenClaw 等 AI 客户端直接调用。

**可用工具**

| 工具 | 说明 |
|------|------|
| `process_video(url)` | 下载→转录→AI优化，返回摘要和 task_id |
| `list_tasks(limit)` | 列出最近处理的任务 |
| `get_task(task_id)` | 获取任务详情和完整内容 |
| `chat_content(task_id, question, mode)` | 对指定内容提问（normal / learn 模式） |
| `analyze_content(task_id, type)` | 生成内容分析（summary/outline/qa/extension） |
| `wiki_query(question)` | 在知识库中语义检索相关知识 |
| `wiki_ingest(content, source_type, title, source_url)` | 向知识库写入文章或笔记 |

**Claude Code 接入**（`mcp_config.json` 已就绪）：

```json
{
  "mcpServers": {
    "pkos": {
      "command": "python3",
      "args": ["/path/to/pkos/mcp_server.py"],
      "env": { "PYTHONPATH": "/path/to/pkos" }
    }
  }
}
```

## 目录结构

```
pkos/
├── bot/              # Telegram Bot 模块（消息处理、对话引擎、进度上报）
├── processors/       # 视频处理（下载、转录、LLM 优化）
├── storage/          # 数据库存储（PostgreSQL、Obsidian）
├── models/           # 数据模型（Pydantic）
│   └── whisper-base/ # 本地 Whisper 模型文件（不入 git）
├── config/           # 配置文件
├── docker/           # Dockerfile 和 docker-compose
├── scripts/          # 工具脚本（日志分析等）
└── docs/             # 文档
```

## 常用命令

```bash
# 查看容器日志
docker logs pkos --tail 50 -f

# 分析 LLM 调用成本
python3 scripts/analyze_llm_logs.py log/pkos.log

# 重建镜像（依赖变更后）
docker-compose -f docker/docker-compose.dev.yml build --no-cache
```

## License

MIT
