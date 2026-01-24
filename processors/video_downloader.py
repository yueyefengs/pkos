import re
import asyncio
from typing import Optional, Tuple
from pathlib import Path
from config.settings import settings

class VideoDownloader:
    def __init__(self):
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)

    def detect_platform(self, url: str) -> Optional[str]:
        """检测视频平台"""
        if "douyin.com" in url:
            return "douyin"
        elif "bilibili.com" in url:
            return "bilibili"
        return None

    async def download(self, url: str) -> Tuple[str, str]:
        """下载视频并提取音频

        Returns:
            (音频文件路径, 视频标题)
        """
        platform = self.detect_platform(url)

        if platform == "bilibili":
            return await self._download_bilibili(url)
        elif platform == "douyin":
            return await self._download_douyin(url)
        else:
            raise ValueError(f"不支持的平台: {platform}")

    async def _download_bilibili(self, url: str) -> Tuple[str, str]:
        """下载B站视频"""
        import yt_dlp

        output_template = str(self.temp_dir / "bilibili_%(title)s.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192'
            }],
            'postprocessor_args': ['-ac', '1', '-ar', '16000'],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'unknown')

        # 查找生成的音频文件
        for ext in ['m4a', 'webm', 'mp3', 'wav']:
            audio_file = self.temp_dir / f"bilibili_{title}.{ext}"
            if audio_file.exists():
                return str(audio_file), self._sanitize_title(title)

        raise Exception("未找到下载的音频文件")

    async def _download_douyin(self, url: str) -> Tuple[str, str]:
        """下载抖音视频"""
        import yt_dlp

        # 抖音通常可以用yt-dlp，如果需要cookies
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(self.temp_dir / "douyin_%(id)s.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '192'
            }],
            'postprocessor_args': ['-ac', '1', '-ar', '16000'],
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        # 检查cookies文件
        cookies_file = Path(settings.douyin_cookies_file)
        if cookies_file.exists():
            ydl_opts['cookiefile'] = str(cookies_file)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', info.get('description', 'unknown')[:50])

        # 查找生成的音频文件
        for ext in ['m4a', 'webm', 'mp3', 'wav']:
            for file in self.temp_dir.glob(f"douyin_*.{ext}"):
                return str(file), self._sanitize_title(title)

        raise Exception("未找到下载的音频文件")

    def _sanitize_title(self, title: str) -> str:
        """清理标题为安全的文件名"""
        safe = re.sub(r"[^\w\-\s]", "", title)
        safe = re.sub(r"\s+", "_", safe).strip("._-")
        return safe[:80] or "untitled"

# 全局下载器实例
video_downloader = VideoDownloader()
