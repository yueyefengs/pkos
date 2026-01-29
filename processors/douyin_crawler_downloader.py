"""
抖音视频下载器 - 使用Douyin_TikTok_Download_API的爬虫
"""
import os
import sys
import asyncio
import httpx
from pathlib import Path
from typing import Tuple, Optional
import subprocess
import yaml

# 添加Douyin_TikTok_Download_API到Python路径
DOUYIN_API_PATH = Path(__file__).parent.parent / "Douyin_TikTok_Download_API"
sys.path.insert(0, str(DOUYIN_API_PATH))

from crawlers.douyin.web.web_crawler import DouyinWebCrawler


class DouyinCrawlerDownloader:
    """使用Douyin_TikTok_Download_API的专业爬虫下载抖音视频"""

    def __init__(self, cookies_file: str = None):
        self.crawler = DouyinWebCrawler()
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        self.cookies_file = cookies_file
        self._cookies_updated = False

    async def _update_cookies_from_file(self, cookies_file: str):
        """从Netscape格式的cookies文件读取并更新配置"""
        if self._cookies_updated:
            return

        cookie_dict = {}
        with open(cookies_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = line.split('\t')
                if len(parts) >= 7:
                    name = parts[5]
                    value = parts[6]
                    cookie_dict[name] = value

        # 将cookie字典转换为Cookie字符串
        cookie_string = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])

        # 更新crawler的配置
        await self.crawler.update_cookie(cookie_string)
        self._cookies_updated = True

    async def download(self, url: str) -> Tuple[str, str]:
        """
        下载抖音视频并提取音频

        Args:
            url: 抖音视频URL（短链接或长链接）

        Returns:
            (音频文件路径, 视频标题)
        """
        # 0. 如果有cookies文件，先更新cookies
        if self.cookies_file and Path(self.cookies_file).exists():
            await self._update_cookies_from_file(self.cookies_file)

        # 1. 提取aweme_id
        aweme_id = await self.crawler.get_aweme_id(url)
        if not aweme_id:
            raise ValueError(f"无法从URL提取aweme_id: {url}")

        # 2. 获取视频详情
        video_data = await self.crawler.fetch_one_video(aweme_id)
        if not video_data or 'aweme_detail' not in video_data:
            raise ValueError(f"无法获取视频数据: {aweme_id}")

        detail = video_data['aweme_detail']

        # 3. 提取视频信息
        title = detail.get('desc', f'douyin_{aweme_id}')
        video_info = detail.get('video', {})

        # 优先使用play_addr的url_list（通常是最佳质量）
        play_addr = video_info.get('play_addr', {})
        video_url = None

        if 'url_list' in play_addr and play_addr['url_list']:
            video_url = play_addr['url_list'][0]

        if not video_url:
            # 备选：使用bit_rate中的play_addr
            bit_rate_list = video_info.get('bit_rate', [])
            if bit_rate_list:
                video_url = bit_rate_list[0].get('play_addr', {}).get('url_list', [None])[0]

        if not video_url:
            raise ValueError(f"无法从视频数据中提取下载链接: {aweme_id}")

        # 4. 下载视频
        video_filename = self._sanitize_title(title) + f"_{aweme_id}.mp4"
        video_path = self.temp_dir / video_filename

        await self._download_file(video_url, video_path)

        # 5. 提取音频
        audio_path = video_path.with_suffix('.m4a')
        self._extract_audio(video_path, audio_path)

        # 6. 删除视频文件，保留音频
        if video_path.exists():
            video_path.unlink()

        return str(audio_path), self._sanitize_title(title)

    async def _download_file(self, url: str, save_path: Path):
        """使用httpx下载文件"""
        # 获取抖音的headers
        kwargs = await self.crawler.get_douyin_headers()

        async with httpx.AsyncClient(headers=kwargs['headers'], timeout=60.0, follow_redirects=True) as client:
            async with client.stream('GET', url) as response:
                response.raise_for_status()

                with open(save_path, 'wb') as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

    def _extract_audio(self, video_path: Path, audio_path: Path):
        """使用ffmpeg提取音频"""
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vn',  # 不要视频
            '-acodec', 'aac',  # 使用AAC编码
            '-ac', '1',  # 单声道
            '-ar', '16000',  # 采样率16kHz
            '-y',  # 覆盖已存在的文件
            str(audio_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"ffmpeg音频提取失败: {result.stderr}")

    def _sanitize_title(self, title: str) -> str:
        """清理标题为安全的文件名"""
        import re
        safe = re.sub(r"[^\w\-\s]", "", title)
        safe = re.sub(r"\s+", "_", safe).strip("._-")
        return safe[:80] or "douyin_video"


# 全局实例（懒加载）
_douyin_crawler_downloader: Optional[DouyinCrawlerDownloader] = None


def get_douyin_crawler_downloader(cookies_file: str = None) -> DouyinCrawlerDownloader:
    """获取全局抖音爬虫下载器实例"""
    global _douyin_crawler_downloader
    if _douyin_crawler_downloader is None:
        _douyin_crawler_downloader = DouyinCrawlerDownloader(cookies_file)
    return _douyin_crawler_downloader
