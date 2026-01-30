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

## Common Commands

### Telegram Bot

```bash
# Start Telegram bot
python3 start_telegram_bot.py

# Run in background
nohup python3 start_telegram_bot.py > telegram_bot.log 2>&1 &

# View logs
tail -f telegram_bot.log
```

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

### Environment Setup

```bash
# Install ffmpeg (required for audio extraction)
brew install ffmpeg           # macOS
sudo apt install ffmpeg       # Ubuntu/Debian

# Python dependencies
pip install -r requirements.txt
```

### Docker Deployment

```bash
# Development mode (with code hot-reload)
docker-compose -f docker/docker-compose.dev.yml up

# Production mode
docker-compose -f docker/docker-compose.yml up -d

# Stop services
docker-compose -f docker/docker-compose.yml down
```

**Proxy Configuration for Docker**:
- macOS/Windows: Proxy configured to use `host.docker.internal:7897` (accesses host machine)
- Linux: If proxy connection fails, add to docker-compose.yml:
  ```yaml
  extra_hosts:
    - "host.docker.internal:host-gateway"
  ```
- Proxy environment variables are automatically overridden in container

## Architecture

### Project Structure

```
PKOS/
├── bot/                     # Telegram bot modules
│   ├── telegram_client.py   # Telegram API wrapper
│   ├── telegram_main.py     # Bot entry point
│   ├── command_handlers.py  # Command handlers
│   ├── message_handler.py   # Message routing
│   ├── conversation_engine.py  # LLM conversation
│   ├── content_analysis.py  # Content analysis features
│   ├── progress_tracker.py  # Learning progress
│   └── session_manager.py   # Redis session management
├── processors/              # Video and audio processing
│   ├── video_downloader.py  # Main video downloader (platform detection)
│   ├── douyin_crawler_downloader.py  # Douyin professional scraper (Douyin_TikTok_Download_API)
│   ├── transcriber.py       # Faster-Whisper wrapper
│   └── llm_client.py        # Multi-LLM client
├── storage/                 # Data persistence
│   └── postgres.py          # PostgreSQL operations
├── models/                  # Data models
│   └── task.py             # Task and learning models
├── config/                  # Configuration
│   └── settings.py         # Environment settings
├── docker/                  # Docker configuration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── docker-compose.dev.yml
├── docs/                    # Documentation
│   ├── telegram-bot-setup.md
│   └── douyin-cookies-setup.md
├── AI-Video-Transcriber/    # Web-based video transcriber (FastAPI)
├── summarizer/              # Standalone document summarization service
├── start_telegram_bot.py    # Telegram bot launcher
└── requirements.txt         # Python dependencies
```

### Key Components

**bot/telegram_main.py**
- Main entry point for Telegram bot
- Registers all command handlers
- Manages bot lifecycle (initialization, polling, shutdown)

**bot/command_handlers.py**
- 17 command handlers: /start, /help, /chat, /learn, /history, etc.
- Workspace management: /add, /context, /clear
- Content analysis: /outline, /summary, /qa, /extend
- Progress tracking: /progress, /workspace, /stats, /checkpoint

**bot/conversation_engine.py**
- Dual-mode conversation: Normal (direct Q&A) vs Learning (Socratic teaching)
- LLM integration with conversation history
- Context-aware responses based on workspace articles

**bot/session_manager.py**
- Redis-based session management
- Workspace operations (add/remove/clear articles)
- Conversation history management
- Mode switching (normal/learning)

**processors/video_downloader.py**
- Platform detection (Douyin/Bilibili)
- Routes to appropriate downloader
- Bilibili: yt-dlp with automatic cookie handling
- Douyin: Delegates to douyin_crawler_downloader

**processors/douyin_crawler_downloader.py**
- Professional Douyin scraper using Douyin_TikTok_Download_API
- Bypasses anti-scraping (X-Bogus/A-Bogus algorithms)
- Pipeline: URL→aweme_id→video_data→download→ffmpeg_extract
- Cookie management: Converts Netscape format to crawler config
- Returns m4a audio (mono, 16kHz)

**processors/llm_client.py**
- Multi-LLM support: OpenAI, Claude, DeepSeek, GLM
- Configuration-driven model selection
- Both completion and chat APIs

**storage/postgres.py**
- Task CRUD operations
- Learning progress tracking
- Concept mastery management
- Checkpoint system

### Processing Pipeline

1. **Video Download**:
   - Bilibili: yt-dlp extracts audio directly (m4a format, mono, 16kHz)
   - Douyin: Professional crawler fetches video → ffmpeg extracts audio (m4a, mono, 16kHz)
2. **Transcription**: faster-whisper with VAD, temperature sampling, language detection
3. **Optimization**: LLM corrects typos, completes sentences, intelligent paragraphing
4. **Translation**: Conditional translation via LLM when detected language != target language
5. **Summarization**: AI-generated summary in selected language

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | - |
| `TELEGRAM_BOT_USERNAME` | Telegram bot username (optional) | - |
| `HTTP_PROXY` | HTTP proxy (required in China) | - |
| `HTTPS_PROXY` | HTTPS proxy (required in China) | - |
| `DB_HOST` | PostgreSQL host | `db` (Docker) / `localhost` (local) |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_USER` | Database user | `pkos` |
| `DB_PASSWORD` | Database password | `pkos123` |
| `DB_NAME` | Database name | `pkos_knowledge` |
| `REDIS_HOST` | Redis host | `redis` (Docker) / `localhost` (local) |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_DB` | Redis database number | `0` |
| `LLM_DEFAULT_PROVIDER` | Default LLM provider | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `OPENAI_BASE_URL` | OpenAI API base URL | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o` |
| `CLAUDE_API_KEY` | Claude API key | - |
| `CLAUDE_MODEL` | Claude model name | `claude-3-5-sonnet-20241022` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | - |
| `GLM_API_KEY` | GLM (智谱) API key | - |
| `WHISPER_MODEL_SIZE` | Whisper model size | `base` |

### Cookie Requirements

**Douyin视频下载** (专业爬虫方案):
- 使用Douyin_TikTok_Download_API专业爬虫，绕过抖音反爬虫机制(X-Bogus/A-Bogus算法)
- **必须配置**: 在Chrome浏览器登录抖音后，使用"Get cookies.txt LOCALLY"扩展导出`douyin_cookies.txt`
- Cookie文件位置: `/Users/yueqingli/code/pkos/douyin_cookies.txt` (Netscape格式)
- 系统自动转换cookies到爬虫配置格式并更新
- ⚠️ 由于抖音风控严格，cookies可能需要定期更新

**Bilibili视频**: yt-dlp自动处理，无需配置

See [docs/douyin-cookies-setup.md](docs/douyin-cookies-setup.md) for detailed setup instructions.

### Proxy Configuration (China Mainland)

Telegram API is blocked in China mainland. You must configure a proxy:

```bash
# In .env file
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
```

Common proxy ports:
- Clash: 7890 or 7897
- V2Ray: 1080 or 10808
- Shadowsocks: 1080

## Important Notes

- **FFmpeg is mandatory** for all audio/video operations
- **Long videos** (30-60+ min): Use production mode for stability
- **Task persistence**: Tasks are saved in PostgreSQL - survives service restarts
- **File naming**: Sanitized titles with 6-character task ID suffix
- **Translation**: Only triggered when detected language differs from summary language selection
- **Local vs Docker**: Different host configurations (localhost vs container names)
- **Python 3.13 compatibility**: Use python-telegram-bot >= 22.6 and redis[hiredis] >= 5.0.0

## Troubleshooting

### Telegram Bot Not Responding

**Network Connection Error** (`httpx.ConnectError`):
1. **In China**: Configure proxy in `.env`:
   ```bash
   HTTP_PROXY=http://127.0.0.1:7897
   HTTPS_PROXY=http://127.0.0.1:7897
   ```
2. Verify proxy is running: `curl -x http://127.0.0.1:7897 https://api.telegram.org`
3. Check if proxy port is correct (Clash usually uses 7890 or 7897)

**Other Issues**:
1. Check if bot process is running: `ps aux | grep telegram_bot`
2. Check logs: `tail -f telegram_bot.log`
3. Verify database and Redis are accessible
4. Restart bot: `pkill -f start_telegram_bot && python3 start_telegram_bot.py`

### Douyin Video Download Fails

**"Fresh cookies are needed" Error**:
1. **Automatic (Recommended)**: Ensure you're logged in to douyin.com in Chrome
   - yt-dlp will automatically read cookies from browser
   - No manual export needed
2. **Manual fallback**: If automatic fails, export cookies:
   - Install "Get cookies.txt LOCALLY" extension
   - Login to www.douyin.com
   - Export cookies to `douyin_cookies.txt`
   - See [docs/douyin-cookies-setup.md](docs/douyin-cookies-setup.md)
3. Verify cookies: `yt-dlp --cookies-from-browser chrome --get-title "抖音视频链接"`

### Database Connection Issues
- For local execution: Use `DB_HOST=localhost`
- For Docker execution: Use `DB_HOST=db`
- Ensure PostgreSQL is running and accessible on port 5432
