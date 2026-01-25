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

# Python dependencies (install in each subdirectory as needed)
pip install faster-whisper yt-dlp anthropic httpx fastapi uvicorn selenium webdriver-manager
```

## Architecture

### Project Structure

```
PKOS/
├── AI-Video-Transcriber/    # Main web-based video transcriber (FastAPI)
│   ├── backend/              # Core processing modules
│   │   ├── main.py          # FastAPI app with SSE for real-time progress
│   │   ├── video_processor.py  # yt-dlp integration
│   │   ├── transcriber.py   # Faster-Whisper speech-to-text
│   │   ├── summarizer.py    # OpenAI GPT-4o for text optimization
│   │   └── translator.py    # GPT-4o translation
│   ├── static/              # Frontend (HTML/JS)
│   ├── temp/                # Temporary audio/video files
│   └── start.py             # Startup script
├── summarizer/              # Standalone document summarization service
│   ├── backend/
│   │   ├── main.py          # FastAPI with multi-LLM support
│   │   └── config.json      # LLM configurations
│   ├── frontend/            # Web UI
│   └── start.py             # Startup script
├── bili2text/               # Legacy Bilibili-specific transcriber (Tkinter GUI)
├── video_transcriber.py     # Generic CLI video transcriber
├── bilibili_downloader.py    # Bilibili CLI downloader
├── douyin_downloader.py     # Douyin CLI downloader (Selenium-based)
├── prompt/                  # Prompt templates for different content types
└── outputs/                 # Default output directory
```

### Key Components

**AI-Video-Transcriber/backend/main.py**
- FastAPI application with SSE (Server-Sent Events) for real-time progress
- Task queue system with persistent state via `temp/tasks.json`
- Processes: download → transcribe → optimize → summarize → (optionally translate)
- Output files: `transcript_{title}_{id}.md`, `summary_{title}_{id}.md`, `translation_{title}_{id}.md`

**summarizer/backend/main.py**
- Multi-LLM support: OpenAI, Claude, DeepSeek, GLM, custom OpenAI-compatible APIs
- Configuration-driven via `config.json`
- API endpoints: `/api/summarize`, `/api/test`, `/api/files`

**video_transcriber.py**
- Standalone CLI tool
- Uses faster-whisper with configurable model size (tiny/base/small/medium/large)
- VAD (Voice Activity Detection) filtering enabled
- Outputs both .md and .txt files

### Processing Pipeline

1. **Video Download**: yt-dlp extracts audio directly (m4a format, mono, 16kHz)
2. **Transcription**: faster-whisper with VAD, temperature sampling, language detection
3. **Optimization**: OpenAI GPT-4o corrects typos, completes sentences, intelligent paragraphing
4. **Translation**: Conditional translation via GPT-4o when detected language != target language
5. **Summarization**: AI-generated summary in selected language

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | Required for AI features (summarization, optimization, translation) | - |
| `OPENAI_BASE_URL` | Custom OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `HOST` | Server host address | `0.0.0.0` |
| `PORT` | Server port | `8000` (AI-Video-Transcriber), `8001` (summarizer) |
| `WHISPER_MODEL_SIZE` | Whisper model size | `base` |

### Cookie Requirements

- **Douyin**: Requires `www.douyin.com_cookies.txt` (export via "Get cookies.txt LOCALLY" browser extension)
- **Bilibili**: yt-dlp handles cookies automatically, but `--cookies-from-browser chrome` option available

## Prompt Templates

The `prompt/` directory contains specialized summarization strategies:
- `explain_theory_strategy.md` - Theory explanation
- `skill_execution_strategy.md` - Skill/tutorial content
- `finance_risk_strategy.md` - Financial risk analysis
- `biography_transfer_strategy.md` - Biography content
- `opinion_analysis_strategy.md` - Opinion/argument analysis

These are used by the LLM to adapt summarization style based on content type.

## Important Notes

- **FFmpeg is mandatory** for all audio/video operations
- **Long videos** (30-60+ min): Use `--prod` flag to avoid SSE disconnections
- **Task persistence**: Tasks are saved in `temp/tasks.json` - survives service restarts
- **File naming**: Sanitized titles with 6-character task ID suffix
- **Translation**: Only triggered when detected language differs from summary language selection
- **Output location**: AI-Video-Transcriber outputs to `temp/`; CLI tools output to `outputs/` or specified directory
