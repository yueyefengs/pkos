#!/usr/bin/env python3
"""
B站视频下载工具 V2
使用 yt-dlp 作为下载后端
"""

import re
import os
import sys
import subprocess


class BilibiliDownloader:
    """B站视频下载器 - 基于 yt-dlp"""

    def __init__(self):
        self.check_ytdlp()

    def check_ytdlp(self):
        """检查 yt-dlp 是否已安装"""
        try:
            result = subprocess.run(
                ['yt-dlp', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"使用 yt-dlp 版本: {result.stdout.strip()}")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        print("警告: 未找到 yt-dlp，正在尝试安装...")
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '-U', 'yt-dlp'],
                check=True,
                timeout=120
            )
            print("yt-dlp 安装成功!")
            return True
        except Exception as e:
            print(f"无法安装 yt-dlp: {e}")
            print("\n请手动安装 yt-dlp:")
            print("  pip install yt-dlp")
            print("  或: brew install yt-dlp")
            sys.exit(1)

    def extract_video_id(self, input_text):
        """
        从输入文本中提取视频ID或URL
        """
        input_text = input_text.strip()

        # 提取URL
        url_match = re.search(r'https?://[^\s]+', input_text)
        if url_match:
            return url_match.group(0)

        # 返回BV号
        bv_match = re.search(r'(BV[a-zA-Z0-9]{10})', input_text, re.IGNORECASE)
        if bv_match:
            return f'https://www.bilibili.com/video/{bv_match.group(1).upper()}'

        # 返回AV号
        av_match = re.search(r'av(\d+)', input_text, re.IGNORECASE)
        if av_match:
            return f'https://www.bilibili.com/video/av{av_match.group(1)}'

        return None

    def get_video_info(self, url):
        """
        获取视频信息
        """
        cmd = [
            'yt-dlp',
            '--dump-json',
            '--no-download',
            '--no-playlist',
            url
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                return {
                    'title': data.get('title', 'B站视频'),
                    'uploader': data.get('uploader', '未知作者'),
                    'duration': data.get('duration', 0),
                    'description': data.get('description', ''),
                    'thumbnail': data.get('thumbnail', ''),
                    'chapters': data.get('chapters', []),
                    'playlist_count': data.get('playlist_count', 0),
                }
        except subprocess.TimeoutExpired:
            print("  获取视频信息超时")
        except Exception as e:
            print(f"  获取视频信息出错: {e}")

        return None

    def sanitize_filename(self, filename):
        """
        清理文件名
        """
        # 移除或替换不合法字符
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.strip()
        # 限制文件名长度
        if len(filename) > 200:
            filename = filename[:200]
        return filename

    def download(self, input_text, output_dir='./downloads'):
        """
        主下载流程
        """
        print("=" * 60)
        print("B站视频下载工具 (基于 yt-dlp)")
        print("=" * 60)

        # 1. 解析输入
        print("\n[1/4] 解析输入...")
        url = self.extract_video_id(input_text)
        if not url:
            print("  错误: 无法识别视频ID或链接")
            return False
        print(f"  视频链接: {url}")

        # 2. 获取视频信息
        print("\n[2/4] 获取视频信息...")
        video_info = self.get_video_info(url)
        if video_info:
            print(f"  标题: {video_info['title'][:60]}...")
            print(f"  作者: {video_info['uploader']}")
            if video_info['duration']:
                import datetime
                duration = datetime.timedelta(seconds=video_info['duration'])
                print(f"  时长: {duration}")

            if video_info['playlist_count'] > 1:
                print(f"  播放列表: {video_info['playlist_count']} 个视频")
        else:
            print("  警告: 无法获取视频信息，将直接尝试下载")
            video_info = {'title': 'B站视频'}

        # 3. 准备下载
        print("\n[3/4] 准备下载...")
        os.makedirs(output_dir, exist_ok=True)

        title = self.sanitize_filename(video_info['title'])
        if not title:
            title = 'bilibili_video'

        output_template = os.path.join(output_dir, f'{title}.%(ext)s')

        # 4. 下载视频
        print("\n[4/4] 开始下载...")

        cmd = [
            'yt-dlp',
            '--no-warnings',
            '--no-playlist',
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            '--merge-output-format', 'mp4',
            '-o', output_template,
            url
        ]

        try:
            # 直接运行yt-dlp，显示实时进度
            result = subprocess.run(
                cmd,
                timeout=600  # 10分钟超时
            )

            if result.returncode == 0:
                print("\n" + "=" * 60)
                print("下载成功!")

                # 查找下载的文件
                for file in os.listdir(output_dir):
                    if title in file and file.endswith('.mp4'):
                        file_path = os.path.join(output_dir, file)
                        size = os.path.getsize(file_path)
                        size_mb = size / (1024 * 1024)
                        print(f"文件: {file}")
                        print(f"大小: {size_mb:.2f} MB")
                        print(f"路径: {file_path}")
                        break
                return True
            else:
                print(f"\n下载失败，返回码: {result.returncode}")
                print("\n可能的原因:")
                print("1. 需要登录或VIP权限")
                print("2. 视频存在地区限制")
                print("3. 网络连接问题")
                return False

        except subprocess.TimeoutExpired:
            print("\n下载超时")
            return False
        except KeyboardInterrupt:
            print("\n用户取消下载")
            return False
        except Exception as e:
            print(f"\n下载出错: {e}")
            return False


def main():
    if len(sys.argv) < 2:
        print("B站视频下载工具")
        print("\n使用方法:")
        print("  python bilibili_downloader.py 'B站视频链接或ID'")
        print("\n支持的输入格式:")
        print("  - BV号: BV1xx411c7mD")
        print("  - AV号: av12345678")
        print("  - 短链接: https://b23.tv/08VJetn")
        print("  - 完整链接: https://www.bilibili.com/video/BV1xx411c7mD")
        print("\n示例:")
        print('  python bilibili_downloader.py "https://www.bilibili.com/video/BV1xx411c7mD"')
        print('  python bilibili_downloader.py "BV1xx411c7mD"')
        print('  python bilibili_downloader.py "https://b23.tv/08VJetn"')
        sys.exit(1)

    input_text = ' '.join(sys.argv[1:])
    downloader = BilibiliDownloader()
    downloader.download(input_text)


if __name__ == '__main__':
    main()
