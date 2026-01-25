#!/usr/bin/env python3
"""
抖音无水印视频下载工具 V4
使用 Selenium + 网络拦截
"""

import re
import os
import sys
import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities


class DouyinDownloader:
    """抖音视频下载器 - 网络拦截版本"""

    def __init__(self):
        self.session = requests.Session()
        self.video_url = None

    def setup_driver(self):
        """设置Chrome浏览器并启用网络日志"""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        # 启用网络日志
        options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        # 加载cookies
        if os.path.exists('www.douyin.com_cookies.txt'):
            driver.get('https://www.douyin.com')
            self.load_cookies_to_driver(driver, 'www.douyin.com_cookies.txt')

        return driver

    def load_cookies_to_driver(self, driver, cookie_file):
        """加载cookies到浏览器"""
        try:
            import http.cookiejar as cookiejar
            cookie_jar = cookiejar.MozillaCookieJar()
            cookie_jar.load(cookie_file, ignore_discard=True, ignore_expires=True)

            count = 0
            for cookie in cookie_jar:
                try:
                    if cookie.value:
                        driver.add_cookie({
                            'name': cookie.name,
                            'value': cookie.value,
                            'domain': cookie.domain,
                            'path': cookie.path,
                            'secure': cookie.secure or False,
                        })
                        count += 1
                except:
                    pass

            print(f"成功加载 {count} 个cookies")
        except Exception as e:
            print(f"加载cookies失败: {e}")

    def extract_url(self, share_text):
        """提取抖音链接"""
        pattern = r'https?://v\.douyin\.com/[a-zA-Z0-9/]+'
        match = re.search(pattern, share_text)
        if match:
            return match.group(0)

        pattern = r'https?://[a-zA-Z0-9.-]*douyin[a-zA-Z0-9.-]*/[^\s]+'
        match = re.search(pattern, share_text)
        if match:
            return match.group(0).rstrip('/')

        return None

    def find_video_url_from_logs(self, driver):
        """从浏览器日志中查找视频URL"""
        logs = driver.get_log('performance')
        video_requests = []

        for entry in logs:
            try:
                log = json.loads(entry['message'])['message']

                # 查找请求 - 包含video_id的
                if log['method'] == 'Network.requestWillBeSent':
                    request = log['params']['request']
                    url = request.get('url', '')

                    # 查找包含play或video_id的视频URL
                    if ('/play' in url or 'video_id=' in url) and '.mp4' in url:
                        # 排除静态资源
                        if 'douyinstatic.com' not in url and 'uuu_' not in url:
                            # 转换为无水印链接
                            clean_url = url.split('?')[0]  # 移除参数
                            clean_url = clean_url.replace('playwm', 'play')
                            video_requests.append(clean_url)
                            print(f"  找到视频请求: {clean_url[:80]}...")

            except:
                pass

        # 去重
        if video_requests:
            # 优先选择包含playwm的（然后我们替换为play）
            for url in video_requests:
                if 'playwm' in url:
                    return url.replace('playwm', 'play')
            return video_requests[0]

        return None

    def get_video_info_from_page(self, driver, url):
        """从网页获取视频信息"""
        try:
            print(f"  正在访问: {url}")
            driver.get(url)

            # 等待页面加载
            print("  等待视频加载...")
            time.sleep(10)

            # 首先尝试执行JavaScript获取video元素
            print("  尝试获取video元素...")
            try:
                js_code = '''
                // 查找所有video元素
                const videos = document.querySelectorAll('video');
                if (videos.length > 0) {
                    for (let i = 0; i < videos.length; i++) {
                        const v = videos[i];
                        if (v.src && v.src.length > 100) {
                            return v.src;
                        }
                        // 检查source子元素
                        const sources = v.querySelectorAll('source');
                        for (let s of sources) {
                            if (s.src && s.src.length > 100) {
                                return s.src;
                            }
                        }
                    }
                }
                return null;
                '''

                video_src = driver.execute_script(js_code)
                if video_src:
                    print(f"  找到video src: {video_src[:80]}...")
                    return {
                        'desc': '抖音视频',
                        'video': {
                            'play_addr': {
                                'url_list': [video_src]
                            }
                        },
                        'author': {
                            'nickname': '未知作者'
                        }
                    }
            except Exception as e:
                print(f"  JavaScript执行失败: {e}")

            # 尝试从日志中查找视频URL
            print("  正在捕获网络请求...")
            video_url = self.find_video_url_from_logs(driver)

            if video_url:
                return {
                    'desc': '抖音视频',
                    'video': {
                        'play_addr': {
                            'url_list': [video_url]
                        }
                    },
                    'author': {
                        'nickname': '未知作者'
                    }
                }

            return None

        except Exception as e:
            print(f"  页面解析失败: {e}")
            return None

    def download_video(self, video_url, save_path):
        """下载视频"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Referer': 'https://www.douyin.com/',
        }

        try:
            response = self.session.get(video_url, headers=headers, stream=True, timeout=30)

            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))

                with open(save_path, 'wb') as f:
                    if total_size > 0:
                        downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                progress = (downloaded / total_size) * 100
                                print(f"\r  下载进度: {progress:.1f}%", end='', flush=True)
                    else:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                print(f"\n  下载完成!")
                return True
            else:
                print(f"  下载失败，状态码: {response.status_code}")

        except Exception as e:
            print(f"  下载异常: {e}")

        return False

    def sanitize_filename(self, filename):
        """清理文件名"""
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = filename.strip()
        if len(filename) > 200:
            filename = filename[:200]
        return filename

    def download(self, share_text, output_dir='./downloads'):
        """主下载流程"""
        print("=" * 60)
        print("抖音无水印视频下载器 V4")
        print("=" * 60)

        # 1. 提取URL
        print("\n[1/4] 解析分享链接...")
        share_url = self.extract_url(share_text)
        if not share_url:
            print("  错误: 无法提取抖音链接")
            return False
        print(f"  分享链接: {share_url}")

        # 2. 启动浏览器
        print("\n[2/4] 启动浏览器...")
        driver = self.setup_driver()

        try:
            # 3. 获取视频数据
            print("\n[3/4] 获取视频信息...")
            video_data = self.get_video_info_from_page(driver, share_url)

            if not video_data:
                print("  错误: 无法获取视频信息")
                return False

            # 解析视频信息
            desc = video_data.get('desc', '抖音视频')
            author_info = video_data.get('author', {})
            author_name = author_info.get('nickname', '未知作者')

            print(f"  标题: {desc[:50]}...")
            print(f"  作者: {author_name}")

            # 4. 下载视频
            print("\n[4/4] 开始下载...")
            os.makedirs(output_dir, exist_ok=True)

            # 获取视频下载链接
            video_info = video_data.get('video', {})
            play_addr = video_info.get('play_addr', {})
            url_list = play_addr.get('url_list', [])

            if not url_list:
                print("  错误: 未找到视频下载链接")
                return False

            download_url = url_list[0]
            download_url = download_url.replace('playwm', 'play')
            print(f"  下载链接: {download_url[:80]}...")

            title = self.sanitize_filename(desc)
            if not title:
                title = 'douyin_video'

            save_path = os.path.join(output_dir, f'{title}.mp4')

            if os.path.exists(save_path):
                print(f"  文件已存在")
                overwrite = input("  是否覆盖? (y/n): ").strip().lower()
                if overwrite != 'y':
                    print("  下载已取消")
                    return False

            print(f"  保存路径: {save_path}")

            if self.download_video(download_url, save_path):
                file_size = os.path.getsize(save_path)
                if file_size > 1000:
                    size_mb = file_size / (1024 * 1024)
                    print(f"\n成功下载到: {save_path}")
                    print(f"文件大小: {size_mb:.2f} MB")
                    return True
                else:
                    print(f"\n警告: 文件大小异常")
                    os.remove(save_path)

            return False

        finally:
            driver.quit()


def main():
    if len(sys.argv) < 2:
        print("抖音无水印视频下载器 V4")
        print("\n使用方法:")
        print("  python douyin_downloader.py '抖音分享链接'")
        sys.exit(1)

    share_text = ' '.join(sys.argv[1:])
    downloader = DouyinDownloader()
    downloader.download(share_text)


if __name__ == '__main__':
    main()
