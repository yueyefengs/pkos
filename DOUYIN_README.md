# 抖音无水印视频下载器

## 使用方法

### 基本用法
```bash
python3 douyin_downloader.py "抖音分享文本或链接"
```

### 示例
```bash
python3 douyin_downloader.py "3.38 复制打开抖音 https://v.douyin.com/xxxxx/"
```

## 关于抖音视频下载

抖音使用了较强的反爬虫机制，需要**登录cookies**才能下载视频。以下是几种解决方案：

### 方案1: 使用浏览器Cookies (推荐)

1. 安装浏览器扩展 "Get cookies.txt LOCALLY"
   - Chrome: https://chrome.google.com/webstore
   - Firefox: https://addons.mozilla.org

2. 访问 https://www.douyin.com 并登录

3. 点击扩展图标，导出 `cookies.txt` 文件

4. 将 `cookies.txt` 放在脚本同目录下

5. 重新运行下载命令

### 方案2: 直接使用 yt-dlp 命令

```bash
# 使用Chrome浏览器中的cookies
yt-dlp --cookies-from-browser chrome "抖音视频链接"

# 或使用Firefox
yt-dlp --cookies-from-browser firefox "抖音视频链接"
```

### 方案3: 手动下载 (最简单)

1. 打开抖音网页版 https://www.douyin.com
2. 找到想下载的视频
3. 按F12打开开发者工具
4. 切换到Network标签
5. 播放视频，查找视频文件请求
6. 右键复制链接地址
7. 使用下载工具下载

## 脚本功能

- 自动解析抖音分享链接
- 支持多种分享文本格式
- 自动转换为无水印下载链接
- 支持使用cookies文件
- 下载失败时自动尝试备用方法

## 依赖安装

```bash
pip install yt-dlp requests
# 或
pip3 install yt-dlp requests
```

## 文件说明

- `douyin_downloader.py` - 主下载脚本
- `cookies.txt` - 浏览器cookies文件（需要自己导出）
- `downloads/` - 默认下载目录
