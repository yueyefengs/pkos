# PKOS MCP Server 设计文档
**日期**: 2026-03-05
**目标**: 将 PKOS 服务通过 MCP HTTP transport 暴露给本地 OpenClaw AI agent 调用

---

## 背景

PKOS 是一个视频转知识的处理系统，目前通过 Telegram Bot 交互。用户希望将其核心能力以 MCP 工具的形式暴露给本地 OpenClaw AI agent，使其可以通过任意聊天频道（WhatsApp、Telegram、Discord 等）触发视频处理和知识问答。

OpenClaw 原生支持 MCP servers，无需修改 OpenClaw 本身。

---

## 架构

```
用户（WhatsApp / Telegram / Discord 等）
        ↓
   OpenClaw AI Agent（本机）
        ↓ MCP HTTP transport（localhost:9000）
   mcp_server.py（Docker 容器内，port 9000）
        ↓ 直接 Python import
   video_downloader / transcriber / content_processor / LLMClient / PostgreSQL
```

### 为什么选 MCP HTTP transport（而非 stdio）

| 项目 | stdio | HTTP |
|------|-------|------|
| MCP server 在哪 | 本机（spawn 子进程） | 任意位置（URL 指向） |
| 适合 Docker 部署 | ❌ 需本地安装全部依赖 | ✅ 完全在 Docker 内 |
| 调试 | 难（stdin/stdout） | 易（curl 可测） |
| 本机零依赖 | ❌ | ✅ |

---

## 改动范围

### 1. `mcp_server.py`（重写）

从 stdio transport 改为 **MCP HTTP transport**，使用 Python MCP SDK 的 FastAPI 集成（`FastMCP` 或 `mcp.server.fastapi`）。

暴露 5 个工具：

| 工具名 | 功能 | 关键参数 |
|--------|------|----------|
| `process_video` | 处理视频：下载→转录→优化→生成分析 | `url: str` |
| `list_tasks` | 列出最近已处理的视频任务 | `limit: int = 10` |
| `get_task` | 获取指定任务的完整内容 | `task_id: int` |
| `chat_content` | 基于视频内容回答问题 | `task_id: int`, `question: str`, `mode: str` |
| `analyze_content` | 生成大纲/总结/问答/扩展 | `task_id: int`, `type: str` |

工具直接 import 并调用已有 Python 模块（`video_downloader`、`transcriber`、`content_processor`、`PostgresStorage`、`ConversationEngine`、`ContentAnalyzer`），**无需新增 HTTP API 层**。

### 2. `docker-compose.yml` / `docker-compose.dev.yml`

暴露 port 9000（MCP HTTP），映射到 `localhost:9000`：

```yaml
ports:
  - "9000:9000"
```

启动命令新增 MCP server 进程，或通过 supervisor 同时运行 Telegram bot 和 MCP server。

### 3. OpenClaw 配置（`~/.openclaw/openclaw.json`）

```json
{
  "mcp": {
    "servers": {
      "pkos": {
        "url": "http://localhost:9000",
        "transport": "http"
      }
    }
  }
}
```

---

## 关键决策

### process_video 同步还是异步？

采用**同步**：agent 调用后等待完成，返回处理结果。

理由：
- MCP 工具调用无超时限制（由 agent 框架控制）
- 同步更简单，agent 拿到结果后直接使用，无需轮询
- 视频处理通常 1-5 分钟，可接受

### MCP server 如何与 Telegram bot 共存？

两种方案：
- **方案 1**（推荐）：用 `supervisord` 在同一容器内并行运行 Telegram bot 进程和 MCP server 进程
- **方案 2**：在 `telegram_main.py` 启动时用 `asyncio` 同时启动 MCP HTTP server

推荐方案 1，职责分离，互不影响。

### 不需要鉴权

MCP server 只监听 localhost（Docker port mapping），本机内网访问，不加鉴权。

---

## 文件改动清单

```
修改:
  mcp_server.py                    # 从 stdio 改为 HTTP transport，重写工具实现
  docker/docker-compose.yml        # 暴露 port 9000，添加 supervisord 启动
  docker/docker-compose.dev.yml    # 同上
  requirements.txt                 # 确认 mcp[http] 依赖已包含

新增:
  docker/supervisord.conf          # 管理 Telegram bot + MCP server 两个进程

用户操作:
  ~/.openclaw/openclaw.json        # 添加 pkos MCP server 配置
```

---

## 不改动的部分

- Telegram bot 逻辑（`bot/` 目录）
- 所有处理模块（`processors/`）
- 数据模型和存储（`models/`、`storage/`）
- 配置系统（`config/`）
- PostgreSQL / Redis 服务
