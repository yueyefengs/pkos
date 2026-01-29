# 抖音Cookies配置指南

## 为什么需要Cookies？

抖音为了防止爬虫，要求下载视频时必须提供有效的浏览器cookies。这些cookies证明您已经登录并有权访问内容。

## 🚀 快速配置（推荐方法）

### 步骤1: 安装浏览器扩展

**Chrome/Edge用户**:
1. 访问 [Chrome Web Store](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. 点击"添加至Chrome"安装扩展
3. 扩展名称: "Get cookies.txt LOCALLY"

**Firefox用户**:
1. 访问 [Firefox Add-ons](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)
2. 点击"添加到Firefox"
3. 扩展名称: "cookies.txt"

**Safari用户**:
- 可以使用手动方法（见下文）

### 步骤2: 登录抖音

1. 打开浏览器访问: https://www.douyin.com
2. 点击右上角登录
3. 使用以下任一方式登录:
   - 手机号验证码
   - 扫码登录
   - 第三方账号（微信/QQ/微博）

**注意**: 确保登录成功后能看到个人主页

### 步骤3: 导出Cookies

1. **在抖音页面**，点击浏览器工具栏中的扩展图标
2. 找到"Get cookies.txt LOCALLY"扩展
3. 点击扩展，选择以下选项之一:
   - "Export" 或
   - "Export cookies for this site"
4. 浏览器会下载一个 `www.douyin.com_cookies.txt` 文件

### 步骤4: 放置文件

```bash
# 进入项目目录
cd /Users/yueqingli/code/pkos

# 重命名并移动文件（根据实际下载位置调整）
mv ~/Downloads/www.douyin.com_cookies.txt ./douyin_cookies.txt

# 或者直接移动（如果扩展已命名为douyin_cookies.txt）
mv ~/Downloads/douyin_cookies.txt ./
```

### 步骤5: 验证配置

```bash
# 检查文件是否存在
ls -lh douyin_cookies.txt

# 查看文件内容（前几行应该是cookie数据）
head -5 douyin_cookies.txt
```

文件应该包含类似这样的内容:
```
# Netscape HTTP Cookie File
.douyin.com	TRUE	/	FALSE	1735459200	ttwid	1%7C...
.douyin.com	TRUE	/	FALSE	0	__ac_nonce	...
```

## 🔄 刷新Cookies

Cookies会过期，如果遇到以下错误:
```
ERROR: Fresh cookies are needed
```

解决方法:
1. 重新在浏览器登录抖音
2. 重新导出cookies
3. 替换旧的 `douyin_cookies.txt` 文件

## 📱 手动方法（备选）

如果不想安装扩展，可以手动复制cookies:

### 步骤1: 获取Cookies

1. 登录 https://www.douyin.com
2. 打开浏览器开发者工具（F12）
3. 切换到"Network"（网络）标签
4. 刷新页面
5. 选择任一请求，查看"Request Headers"
6. 找到"Cookie"字段，复制完整内容

### 步骤2: 转换格式

创建文件 `douyin_cookies.txt`，格式如下:

```
# Netscape HTTP Cookie File
# 这里粘贴从浏览器复制的cookie值
# 格式: domain	flag	path	secure	expiration	name	value
```

**注意**: 手动方法较复杂且容易出错，推荐使用浏览器扩展。

## 🔐 安全提示

1. **不要分享cookies文件**: cookies包含您的登录凭证
2. **不要提交到Git**: 已在 `.gitignore` 中配置
3. **定期更新**: 建议每月更新一次cookies
4. **保护隐私**: 使用完毕后可删除cookies文件

## 🎯 测试

配置完成后，在Telegram bot中测试:

```
发送抖音视频链接:
https://www.douyin.com/video/7505737012671008050
```

如果配置正确，bot会开始下载和处理视频。

## ❓ 常见问题

### Q1: 导出的cookies文件格式不对？
**A**: 确保使用"Get cookies.txt LOCALLY"扩展，它会自动生成正确格式。

### Q2: 还是提示需要fresh cookies？
**A**:
1. 确认您已成功登录抖音
2. 重新导出cookies
3. 检查cookies文件是否包含`ttwid`等关键字段

### Q3: 能用其他人的cookies吗？
**A**: 理论上可以，但不推荐。每个账号的cookies是独立的，且可能涉及隐私和安全问题。

### Q4: B站视频需要cookies吗？
**A**: B站大部分视频不需要cookies，除非是会员专享或有地区限制的内容。

## 📚 相关资源

- [yt-dlp文档](https://github.com/yt-dlp/yt-dlp#usage-and-options)
- [Get cookies.txt LOCALLY扩展](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
- [cookies.txt格式说明](http://www.cookiecentral.com/faq/#3.5)

## 🛠️ 故障排除

如果配置后仍然失败，请检查:

```bash
# 1. 文件权限
ls -l douyin_cookies.txt
# 应该可读: -rw-r--r--

# 2. 文件位置
pwd
# 应该在: /Users/yueqingli/code/pkos

# 3. 文件内容
head -3 douyin_cookies.txt
# 应该看到cookie数据，不是空文件

# 4. 查看bot日志
tail -f telegram_bot.log
# 查看详细错误信息
```

## 💡 提示

- **首次配置**: 可能需要尝试2-3次才能成功
- **定期维护**: 建议每月检查一次cookies是否过期
- **备用方案**: 如果抖音不行，可以优先使用B站视频测试
