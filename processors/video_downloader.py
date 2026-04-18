import re
import asyncio
import logging
from typing import Optional, Tuple, Callable
from pathlib import Path
from config.settings import settings

logger = logging.getLogger(__name__)

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
        elif "youtube.com" in url or "youtu.be" in url:
            return "youtube"
        return None

    async def download(self, url: str, progress_callback: Optional[Callable] = None) -> Tuple[str, str]:
        """下载视频并提取音频

        Args:
            url: 视频链接
            progress_callback: 可选进度回调 (stage, text) -> None

        Returns:
            (音频文件路径, 视频标题)
        """
        platform = self.detect_platform(url)

        if platform == "bilibili":
            return await self._download_bilibili(url, progress_callback)
        elif platform == "douyin":
            return await self._download_douyin(url, progress_callback)
        elif platform == "youtube":
            return await self._download_youtube(url, progress_callback)
        else:
            raise ValueError(f"不支持的平台: {platform}")

    async def _download_bilibili(self, url: str, progress_callback: Optional[Callable] = None) -> Tuple[str, str]:
        """下载B站视频（在线程池中运行，不阻塞 event loop）"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._download_bilibili_sync, url, progress_callback
        )

    def _download_bilibili_sync(self, url: str, progress_callback: Optional[Callable] = None) -> Tuple[str, str]:
        """B站下载同步实现，供 run_in_executor 调用"""
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

        if progress_callback:
            def hook(d: dict):
                if d.get('status') == 'downloading':
                    pct = d.get('_percent_str', '').strip()  # e.g. " 45.2%"
                    downloaded = d.get('_downloaded_bytes_str', '')
                    total = d.get('_total_bytes_str', '') or d.get('_total_bytes_estimate_str', '')
                    detail = f"{pct}" if pct else "下载中..."
                    if downloaded and total:
                        detail = f"{pct} ({downloaded} / {total})"
                    progress_callback("downloading", f"正在下载... {detail}")
            ydl_opts['progress_hooks'] = [hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'unknown')

        # 查找生成的音频文件
        for ext in ['m4a', 'webm', 'mp3', 'wav']:
            audio_file = self.temp_dir / f"bilibili_{title}.{ext}"
            if audio_file.exists():
                return str(audio_file), self._sanitize_title(title)

        raise Exception("未找到下载的音频文件")

    async def _download_douyin(self, url: str, progress_callback: Optional[Callable] = None) -> Tuple[str, str]:
        """下载抖音视频 - 先尝试 yt-dlp，失败后 fallback 到专业爬虫"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, self._download_douyin_sync, url, progress_callback
            )
        except Exception as e:
            logger.warning(f"[Downloader] yt-dlp 抖音下载失败，尝试爬虫方案: {e}")
            from processors.douyin_crawler_downloader import DouyinCrawlerDownloader
            crawler = DouyinCrawlerDownloader(cookies_file=settings.douyin_cookies_file)
            return await crawler.download(url)

    def _download_douyin_sync(self, url: str, progress_callback: Optional[Callable] = None) -> Tuple[str, str]:
        """抖音下载同步实现，供 run_in_executor 调用"""
        import yt_dlp

        output_template = str(self.temp_dir / "douyin_%(title)s.%(ext)s")

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

        # 添加 cookies 文件支持，按优先级查找
        for candidate in [
            settings.douyin_cookies_file,
            "www.douyin.com_cookies.txt",
        ]:
            if candidate and Path(candidate).exists():
                ydl_opts['cookiefile'] = candidate
                break

        if progress_callback:
            def hook(d: dict):
                if d.get('status') == 'downloading':
                    pct = d.get('_percent_str', '').strip()
                    downloaded = d.get('_downloaded_bytes_str', '')
                    total = d.get('_total_bytes_str', '') or d.get('_total_bytes_estimate_str', '')
                    detail = f"{pct}" if pct else "下载中..."
                    if downloaded and total:
                        detail = f"{pct} ({downloaded} / {total})"
                    progress_callback("downloading", f"正在下载... {detail}")
            ydl_opts['progress_hooks'] = [hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'unknown')

        # 查找生成的音频文件
        for ext in ['m4a', 'webm', 'mp3', 'wav']:
            audio_file = self.temp_dir / f"douyin_{title}.{ext}"
            if audio_file.exists():
                return str(audio_file), self._sanitize_title(title)

        raise Exception("未找到下载的音频文件")

    async def _download_youtube(self, url: str, progress_callback: Optional[Callable] = None) -> Tuple[str, str]:
        """下载 YouTube 视频"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._download_youtube_sync, url, progress_callback
        )

    def _download_youtube_sync(self, url: str, progress_callback: Optional[Callable] = None) -> Tuple[str, str]:
        """YouTube 下载同步实现，供 run_in_executor 调用"""
        import yt_dlp

        output_template = str(self.temp_dir / "youtube_%(title)s.%(ext)s")

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

        if progress_callback:
            def hook(d: dict):
                if d.get('status') == 'downloading':
                    pct = d.get('_percent_str', '').strip()
                    downloaded = d.get('_downloaded_bytes_str', '')
                    total = d.get('_total_bytes_str', '') or d.get('_total_bytes_estimate_str', '')
                    detail = f"{pct}" if pct else "下载中..."
                    if downloaded and total:
                        detail = f"{pct} ({downloaded} / {total})"
                    progress_callback("downloading", f"正在下载... {detail}")
            ydl_opts['progress_hooks'] = [hook]

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'unknown')

        for ext in ['m4a', 'webm', 'mp3', 'wav']:
            audio_file = self.temp_dir / f"youtube_{title}.{ext}"
            if audio_file.exists():
                return str(audio_file), self._sanitize_title(title)

        raise Exception("未找到下载的音频文件")

    def _sanitize_title(self, title: str) -> str:
        """清理标题为安全的文件名

        限制长度以避免超过文件系统的255字节限制。
        考虑到中文字符占3字节，标题限制为30个字符可确保总文件名不超过150字节。
        """
        safe = re.sub(r"[^\w\-\s]", "", title)
        safe = re.sub(r"\s+", "_", safe).strip("._-")
        # 限制为30个字符，避免文件名过长（特别是中文标题）
        return safe[:30] or "untitled"

# 全局下载器实例
video_downloader = VideoDownloader()
