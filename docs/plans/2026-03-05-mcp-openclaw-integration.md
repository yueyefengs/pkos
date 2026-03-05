# MCP OpenClaw Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 PKOS 的视频处理和知识问答能力通过 MCP HTTP transport 暴露给本地 OpenClaw AI agent，零修改 OpenClaw。

**Architecture:** `mcp_server.py` 使用 FastMCP (Python MCP SDK) 以 streamable-http 传输模式运行在 Docker 容器内（port 9000），直接 import 并复用已有的 Python 处理模块和 PostgreSQL 存储。OpenClaw 通过 `~/.openclaw/openclaw.json` 配置 MCP server URL，无需任何插件或修改 OpenClaw 本身。

**Tech Stack:** Python MCP SDK (`mcp[cli]`), FastMCP, uvicorn, 已有 PostgresStorage / ConversationEngine / ContentAnalyzer 模块

---

## 背景知识

### FastMCP 基本用法

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("server-name")

@mcp.tool()
async def my_tool(param: str) -> str:
    """工具描述（AI 会读这段）"""
    return "result"

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9000)
```

工具的 docstring 就是 AI 看到的描述，参数类型会自动生成 JSON Schema。

### OpenClaw MCP 配置

在 `~/.openclaw/openclaw.json` 里加入：

```json
{
  "mcp": {
    "servers": {
      "pkos": {
        "url": "http://localhost:9000/mcp",
        "transport": "http"
      }
    }
  }
}
```

OpenClaw 会自动发现所有工具并让 AI agent 使用。

---

## Task 1: 添加 MCP 依赖

**Files:**
- Modify: `requirements.txt`

**Step 1: 在 requirements.txt 末尾添加 mcp 依赖**

```
# MCP Server (HTTP transport)
mcp[cli]>=1.0.0
```

`mcp[cli]` 包含 FastMCP、streamable-http transport、uvicorn 等所有需要的组件。

**Step 2: 验证包名正确**

```bash
pip index versions mcp
```

Expected: 显示可用版本列表（确认包名存在）

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "deps: add mcp[cli] for FastMCP HTTP transport"
```

---

## Task 2: 重写 mcp_server.py

**Files:**
- Modify: `mcp_server.py`

这是核心任务。把现有的 stdio skeleton 重写为使用 FastMCP 的 HTTP server，直接调用已有的 Python 模块。

**Step 1: 完整替换 mcp_server.py**

```python
#!/usr/bin/env python3
"""
PKOS MCP Server - HTTP transport mode
供 OpenClaw 等 MCP 客户端调用

运行方式: python3 mcp_server.py
端口: 9000
"""
import asyncio
import json
import logging
from mcp.server.fastmcp import FastMCP
from storage.postgres import PostgresStorage
from processors.video_downloader import video_downloader
from processors.transcriber import transcriber
from processors.content_processor import content_processor
from bot.content_analysis import ContentAnalyzer
from bot.conversation_engine import ConversationEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("pkos-mcp")

mcp = FastMCP("pkos")
analyzer = ContentAnalyzer()
engine = ConversationEngine()


@mcp.tool()
async def process_video(url: str) -> str:
    """处理视频：下载→转录→AI优化→生成大纲/总结/问答。
    支持抖音和B站链接。处理完成后返回摘要和 task_id（后续用于对话和分析）。
    注意：处理需要数分钟，请耐心等待。"""
    logger.info(f"process_video: {url}")
    try:
        # 下载
        audio_path, title = await video_downloader.download(url)
        logger.info(f"Downloaded: {title}")

        # 转录
        raw_content = transcriber.transcribe(audio_path)
        logger.info(f"Transcribed: {len(raw_content)} chars")

        # 优化
        processed_content = await content_processor.process(raw_content, title)
        logger.info(f"Processed: {len(processed_content)} chars")

        # 保存到数据库
        storage = PostgresStorage()
        await storage.connect()
        platform = _detect_platform(url)
        task = await storage.create_task(
            task_id=_generate_task_id(),
            video_url=url,
            title=title,
            platform=platform
        )
        await storage.update_task(
            task.id,
            status="completed",
            title=title,
            content=processed_content,
            raw_transcript=raw_content
        )
        await storage.disconnect()

        # 生成摘要
        summary = await analyzer.generate_summary(processed_content)

        return json.dumps({
            "status": "success",
            "task_id": task.id,
            "title": title,
            "platform": platform,
            "content_length": len(processed_content),
            "summary": summary
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"process_video failed: {e}")
        return json.dumps({"status": "failed", "error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def list_tasks(limit: int = 10) -> str:
    """列出最近已处理完成的视频任务，返回 task_id、标题、平台和完成时间。
    使用 task_id 调用 chat_content 或 analyze_content 进行进一步操作。"""
    logger.info(f"list_tasks: limit={limit}")
    try:
        storage = PostgresStorage()
        await storage.connect()
        tasks = await storage.get_recent_tasks(limit=limit)
        await storage.disconnect()

        if not tasks:
            return "暂无已处理的视频记录。"

        result = []
        for t in tasks:
            completed_str = t.completed_at.strftime('%Y-%m-%d %H:%M') if t.completed_at else "未知"
            result.append({
                "task_id": t.id,
                "title": t.title,
                "platform": t.platform,
                "completed_at": completed_str
            })

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"list_tasks failed: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def get_task(task_id: int) -> str:
    """获取指定任务的完整内容（优化后的转录文本）。
    task_id 来自 list_tasks 的返回结果。"""
    logger.info(f"get_task: task_id={task_id}")
    try:
        storage = PostgresStorage()
        await storage.connect()
        task = await storage.get_task_by_id(task_id)
        await storage.disconnect()

        if not task:
            return f"未找到 task_id={task_id} 的任务。"

        return json.dumps({
            "task_id": task.id,
            "title": task.title,
            "platform": task.platform,
            "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
            "content_length": len(task.content) if task.content else 0,
            "content_preview": task.content[:500] + "..." if task.content and len(task.content) > 500 else task.content
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"get_task failed: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool()
async def chat_content(task_id: int, question: str, mode: str = "normal") -> str:
    """基于视频内容回答问题。
    task_id: 来自 list_tasks 的任务ID。
    question: 你的问题。
    mode: 'normal'（直接回答）或 'learning'（苏格拉底式，通过提问引导思考）。"""
    logger.info(f"chat_content: task_id={task_id}, mode={mode}")
    try:
        storage = PostgresStorage()
        await storage.connect()
        task = await storage.get_task_by_id(task_id)
        await storage.disconnect()

        if not task:
            return f"未找到 task_id={task_id} 的任务。"
        if not task.content:
            return f"任务 {task_id} 没有可用内容，可能还在处理中。"

        response = await engine.generate_response(
            question=question,
            article_content=task.content,
            mode=mode,
            history=[]
        )
        return response

    except Exception as e:
        logger.error(f"chat_content failed: {e}")
        return f"回答失败: {str(e)}"


@mcp.tool()
async def analyze_content(task_id: int, type: str = "summary") -> str:
    """对视频内容生成结构化分析。
    task_id: 来自 list_tasks 的任务ID。
    type 可选值:
    - 'summary': 300-500字精炼总结
    - 'outline': 层级大纲
    - 'qa': 5-8个核心问答对
    - 'extensions': 扩展思考方向（不提供答案，仅指引方向）"""
    logger.info(f"analyze_content: task_id={task_id}, type={type}")
    try:
        storage = PostgresStorage()
        await storage.connect()
        task = await storage.get_task_by_id(task_id)
        await storage.disconnect()

        if not task:
            return f"未找到 task_id={task_id} 的任务。"
        if not task.content:
            return f"任务 {task_id} 没有可用内容。"

        if type == "summary":
            result = await analyzer.generate_summary(task.content)
        elif type == "outline":
            result = await analyzer.generate_outline(task.content)
        elif type == "qa":
            result = await analyzer.generate_qa(task.content)
        elif type == "extensions":
            result = await analyzer.generate_extensions(task.content)
        else:
            return f"未知的分析类型: {type}。可选: summary, outline, qa, extensions"

        return result

    except Exception as e:
        logger.error(f"analyze_content failed: {e}")
        return f"分析失败: {str(e)}"


def _detect_platform(url: str) -> str:
    if "douyin.com" in url or "iesdouyin.com" in url:
        return "douyin"
    elif "bilibili.com" in url or "b23.tv" in url:
        return "bilibili"
    return "unknown"


def _generate_task_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8]


if __name__ == "__main__":
    logger.info("Starting PKOS MCP server on port 9000 (streamable-http)...")
    mcp.run(transport="streamable-http", host="0.0.0.0", port=9000)
```

**Step 2: 检查 storage 模块是否有 get_task_by_id 方法**

```bash
grep -n "get_task_by_id\|get_task_by_task_id" /Users/yueqingli/code/pkos/storage/postgres.py
```

Expected: 找到对应方法。若方法名不同（如 `get_task`），相应调整 mcp_server.py 中的调用。

**Step 3: Commit**

```bash
git add mcp_server.py
git commit -m "feat: rewrite mcp_server.py with FastMCP HTTP transport"
```

---

## Task 3: 更新 Dockerfile 暴露 port 9000

**Files:**
- Modify: `docker/Dockerfile`

**Step 1: 在 EXPOSE 8080 后添加 9000**

在 `docker/Dockerfile` 的 `EXPOSE 8080` 这行后面添加：

```dockerfile
EXPOSE 9000
```

最终结果：
```dockerfile
# 暴露端口
EXPOSE 8080
EXPOSE 9000
```

**Step 2: Commit**

```bash
git add docker/Dockerfile
git commit -m "feat: expose port 9000 for MCP HTTP server"
```

---

## Task 4: 更新 docker-compose.dev.yml

**Files:**
- Modify: `docker/docker-compose.dev.yml`

**Step 1: 在现有 pkos service 后添加 pkos-mcp service**

在 `docker/docker-compose.dev.yml` 的 `redis:` service 之前插入：

```yaml
  pkos-mcp:
    container_name: pkos-mcp
    build:
      context: ..
      dockerfile: docker/Dockerfile
    command: python3 mcp_server.py
    volumes:
      - ..:/app
      - /app/__pycache__
    environment:
      - PYTHONUNBUFFERED=1
      - DB_HOST=db
      - DB_PORT=5432
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - HTTP_PROXY=http://host.docker.internal:7897
      - HTTPS_PROXY=http://host.docker.internal:7897
    env_file:
      - ../.env
    ports:
      - "9000:9000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - db
      - redis
    restart: unless-stopped
```

**Step 2: Commit**

```bash
git add docker/docker-compose.dev.yml
git commit -m "feat: add pkos-mcp service to dev docker-compose"
```

---

## Task 5: 更新 docker-compose.yml（生产环境）

**Files:**
- Modify: `docker/docker-compose.yml`

**Step 1: 在现有 pkos service 后添加 pkos-mcp service**

在 `docker/docker-compose.yml` 的 `redis:` service 之前插入：

```yaml
  pkos-mcp:
    image: ${IMAGE_NAME:-yueyefeng11/pkos:latest}
    container_name: pkos-mcp
    command: python3 mcp_server.py
    ports:
      - "9000:9000"
    env_file:
      - ../.env
    depends_on:
      - db
      - redis
    restart: unless-stopped
    environment:
      - PYTHONUNBUFFERED=1
      - DB_HOST=db
      - DB_PORT=5432
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - HTTP_PROXY=http://host.docker.internal:7897
      - HTTPS_PROXY=http://host.docker.internal:7897
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

**Step 2: Commit**

```bash
git add docker/docker-compose.yml
git commit -m "feat: add pkos-mcp service to prod docker-compose"
```

---

## Task 6: 构建并测试 MCP server

**Step 1: 重新构建 Docker 镜像（包含新依赖）**

```bash
docker-compose -f docker/docker-compose.dev.yml build --no-cache pkos-mcp
```

Expected: Build 成功，无报错

**Step 2: 启动 MCP server 服务**

```bash
docker-compose -f docker/docker-compose.dev.yml up pkos-mcp -d
```

Expected: 容器启动，日志显示 `Starting PKOS MCP server on port 9000`

**Step 3: 查看启动日志**

```bash
docker logs pkos-mcp --tail 20
```

Expected: 看到类似 `Uvicorn running on http://0.0.0.0:9000`

**Step 4: 用 curl 验证 MCP endpoint 可访问**

```bash
curl -s http://localhost:9000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

Expected: 返回 JSON，包含 5 个工具（process_video, list_tasks, get_task, chat_content, analyze_content）

**Step 5: 测试 list_tasks 工具**

```bash
curl -s http://localhost:9000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"list_tasks","arguments":{"limit":5}}}'
```

Expected: 返回最近任务列表（或空列表）

---

## Task 7: 配置 OpenClaw 接入

**Step 1: 打开 OpenClaw 配置文件**

```bash
cat ~/.openclaw/openclaw.json
```

查看现有配置结构，确认 JSON 格式。

**Step 2: 在配置中添加 pkos MCP server**

在 `~/.openclaw/openclaw.json` 的根对象中添加（与其他顶层字段同级）：

```json
"mcp": {
  "servers": {
    "pkos": {
      "url": "http://localhost:9000/mcp",
      "transport": "http"
    }
  }
}
```

**Step 3: 验证 OpenClaw 识别到 PKOS 工具**

重启 OpenClaw 后，在任意聊天频道发送：

```
/tools
```

或询问 AI：

```
你有哪些可用的工具？
```

Expected: 看到 `process_video`、`list_tasks`、`get_task`、`chat_content`、`analyze_content` 等工具

**Step 4: 端到端测试**

在 OpenClaw 的聊天频道发送一条抖音/B站链接，观察 AI 是否自动调用 `process_video` 工具。

---

## 故障排查

### MCP server 启动失败

```bash
docker logs pkos-mcp --tail 50
```

常见原因：
- `mcp` 包未安装：检查 requirements.txt 是否包含 `mcp[cli]`，重新 build
- import 错误：检查 mcp_server.py 中的模块路径是否正确
- 端口冲突：`lsof -i :9000` 检查是否有其他进程占用

### OpenClaw 找不到工具

- 确认 Docker MCP server 在运行：`curl http://localhost:9000/mcp`
- 检查 openclaw.json 格式是否合法（JSON 不允许注释）
- 重启 OpenClaw gateway

### process_video 超时

视频处理时间较长（1-10 分钟），如果 OpenClaw 有调用超时设置，需在配置中增大超时值。

---

## 完成标志

- [ ] `curl http://localhost:9000/mcp` 返回包含 5 个工具的 JSON
- [ ] OpenClaw 的 AI agent 可以看到并调用 pkos 工具
- [ ] `list_tasks` 返回数据库中的历史记录
- [ ] `chat_content` 可以对已处理视频进行问答
