# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PKOS (Personal Knowledge Organization System) is a video-to-knowledge transformation toolkit. The project combines multiple video downloaders, audio transcription, and AI summarization capabilities to convert video content into reusable personal knowledge.

## Core Philosophy

This is a "Learning Content Analysis and Review Assistant" project. When working with this codebase:
- Goal: Convert fragmented video information into reusable personal knowledge
- Approach: Prudent, restrained, and traceable
- Constraint: Do not add facts or conclusions not explicitly expressed in the original content
- Distinguish between opinions and facts
- All "extensions" are limited to proposing thinking directions, not providing answers

## Common Pitfalls and Lessons Learned

### Dependency Management

**Problem**: Incremental dependency fixes lead to multiple rebuild cycles.

**Checklist before integrating external projects**:
1. ✅ Read complete `requirements.txt` from upstream project
2. ✅ Add ALL dependencies at once, not incrementally
3. ✅ Check for system dependencies (ffmpeg, chromium, etc.)
4. ✅ Version lock critical dependencies (e.g., `httpx==0.27.0`)
5. ✅ Document dependency source and sync date in comments

**Example**:
```python
# Douyin专业爬虫依赖 (来源: Douyin_TikTok_Download_API)
# 最后同步: 2026-01-30
# 上游仓库: https://github.com/Evil0ctal/Douyin_TikTok_Download_API
httpx==0.27.0
importlib_resources==6.4.0
# ... all other dependencies
```

### Docker Build in China

**Problem**: Docker build fails accessing `deb.debian.org` from China mainland.

**Solution**: Always use Chinese mirrors in Dockerfile:
```dockerfile
# 使用阿里云镜像源（中国大陆）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources
```

**System dependencies checklist**:
- ✅ ffmpeg (for audio/video processing)
- ✅ Update apt cache before install: `apt-get update`
- ✅ Clean cache after install: `rm -rf /var/lib/apt/lists/*`

### Telegram Message Formatting

**Problem**: Unescaped special characters in error messages cause Telegram API parse errors.

**Solution**: Always escape Markdown special characters in dynamic content:
```python
def _escape_markdown(self, text: str) -> str:
    """Escape Telegram Markdown special characters"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text
```

### File Naming in Docker

**Problem**: Long Chinese filenames (>255 bytes) cause Docker build failures.

**Solution**: Aggressive filename truncation for multi-byte characters:
```python
def _sanitize_title(self, title: str) -> str:
    safe = re.sub(r"[^\w\-\s]", "", title)
    safe = re.sub(r"\s+", "_", safe).strip("._-")
    return safe[:30] or "default_name"  # 30 chars = ~90 bytes for Chinese
```

### Proxy Configuration

**Problem**: Hardcoded proxy in docker-compose.yml affects portability.

**Current approach** (acceptable for personal use):
```yaml
environment:
  - HTTP_PROXY=http://host.docker.internal:7897
  - HTTPS_PROXY=http://host.docker.internal:7897
extra_hosts:
  - "host.docker.internal:host-gateway"
```

**Better approach** (for production):
- Use `.env` file with `HTTP_PROXY=${HTTP_PROXY:-}` syntax
- Document proxy requirements in README

## Common Commands

### Video Downloaders

```bash
# Bilibili video download
python3 bilibili_downloader.py "BV号或链接"

# Douyin video download (requires cookies file)
python3 douyin_downloader.py "抖音分享链接"

# Generic video downloader/transcriber (supports multiple platforms)
python3 video_transcriber.py "视频URL" -o outputs -m base -l zh
```

### Web Services

```bash
# AI Video Transcriber (main web UI)
cd AI-Video-Transcriber
python3 start.py              # Development mode with hot-reload
python3 start.py --prod       # Production mode (stable for long videos)

# Document Summarizer service
cd summarizer
python3 start.py              # Default: port 8001
python3 start.py --port 8002  # Custom port
python3 start.py --reload     # Development mode
```

### Docker Operations

```bash
# Development mode (with code hot-reload)
docker-compose -f docker/docker-compose.dev.yml up --build

# Production mode
docker-compose -f docker/docker-compose.yml up -d

# Rebuild without cache (after dependency changes)
docker-compose -f docker/docker-compose.dev.yml build --no-cache

# Check logs
docker logs pkos --tail 50

# Verify system dependencies
docker exec pkos ffmpeg -version
```

### Environment Setup

```bash
# Install ffmpeg (required for audio extraction)
brew install ffmpeg           # macOS
sudo apt install ffmpeg       # Ubuntu/Debian

# Python dependencies (install in each subdirectory as needed)
pip install faster-whisper yt-dlp anthropic httpx fastapi uvicorn selenium webdriver-manager
```

## Architecture

### Feishu Event Reception Modes

PKOS supports two modes for receiving Feishu events:

1. **WebSocket Long Connection Mode** (Default, Recommended)
   - Uses `lark.ws.Client` to establish a WebSocket connection
   - No public IP or domain required
   - No signature verification or decryption needed
   - Automatic reconnection
   - Configuration: Set `FEISHU_EVENT_MODE=websocket` in `.env`
   - See `docs/feishu-websocket-setup.md` for detailed setup

2. **Webhook Mode** (Traditional)
   - Requires public IP or domain
   - Handles signature verification and encryption/decryption
   - Configuration: Set `FEISHU_EVENT_MODE=webhook` in `.env`
   - Requires `FEISHU_ENCRYPT_KEY` to be set

The system automatically selects the mode based on the `FEISHU_EVENT_MODE` environment variable. Both modes share the same event handler logic, so switching is seamless.

### Project Structure

```
PKOS/
├── bot/              # Telegram机器人模块
├── processors/       # 视频处理模块
│   ├── video_downloader.py
│   └── douyin_crawler_downloader.py  # Douyin专业爬虫
├── models/           # 数据模型
├── storage/          # 数据库存储
├── config/           # 配置文件
├── docker/           # Docker配置
├── Douyin_TikTok_Download_API/  # 外部依赖（Git submodule候选）
└── docs/             # 文档
```

### Key Components

**processors/douyin_crawler_downloader.py**
- Professional Douyin downloader using X-Bogus/A-Bogus algorithms
- Cookie management: Netscape format → crawler config
- Fallback to yt-dlp if crawler fails

**bot/telegram_client.py**
- Markdown message formatting with escape handling
- Long message splitting (4096 char limit)
- Progress reporting with emoji indicators

### Processing Pipeline

1. **Video Download**: yt-dlp or professional crawler (Douyin)
2. **Audio Extraction**: ffmpeg (m4a format, mono, 16kHz)
3. **Transcription**: faster-whisper with VAD filtering
4. **Optimization**: OpenAI GPT-4o corrects typos, intelligent paragraphing
5. **Translation**: Conditional translation when detected language ≠ target
6. **Summarization**: AI-generated summary in selected language

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot API token | - |
| `FEISHU_APP_ID` | Feishu application ID | - |
| `FEISHU_APP_SECRET` | Feishu application secret | - |
| `FEISHU_EVENT_MODE` | Event reception mode: `websocket` or `webhook` | `websocket` |
| `FEISHU_ENCRYPT_KEY` | Encryption key (webhook mode only) | - |
| `FEISHU_BITABLE_TOKEN` | Bitable token for storing transcripts | - |
| `FEISHU_BITABLE_TABLE_ID` | Bitable table ID | - |
| `OPENAI_API_KEY` | Required for AI features | - |
| `OPENAI_BASE_URL` | Custom OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `HTTP_PROXY` | HTTP proxy URL | - |
| `HTTPS_PROXY` | HTTPS proxy URL | - |
| `HOST` | Server host address | `0.0.0.0` |
| `PORT` | Server port | `8080` |
| `WHISPER_MODEL_SIZE` | Whisper model size | `base` |
| `DOUYIN_COOKIES_FILE` | Path to Douyin cookies file | `douyin_cookies.txt` |

### Cookie Requirements

- **Douyin**: Requires `douyin_cookies.txt` (Netscape format)
  - Export via "Get cookies.txt LOCALLY" browser extension
  - Login to www.douyin.com first
  - Cookie有效期约30天，需定期更新

- **Bilibili**: yt-dlp handles cookies automatically
  - Optional: `--cookies-from-browser chrome`

## Important Notes

- **FFmpeg is mandatory** for all audio/video operations
- **Long videos** (30-60+ min): Use `--prod` flag to avoid SSE disconnections
- **Task persistence**: Tasks saved in `temp/tasks.json` - survives service restarts
- **File naming**: Sanitized titles with 6-character task ID suffix
- **Translation**: Only triggered when detected language differs from summary language
- **Output location**: Different tools have different output directories
- **Proxy required**: Telegram API and some video platforms blocked in China
- **Douyin cookies**: Must be refreshed every ~30 days
