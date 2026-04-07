FROM python:3.11-slim

# 使用阿里云镜像源（中国大陆）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制本地预下载的 Whisper 模型（避免构建时联网）
COPY models/whisper-base /root/.cache/huggingface/hub/models--Systran--faster-whisper-base/snapshots/local/

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p temp storage log

# 运行时不联网，使用镜像内缓存的模型
ENV HF_HUB_OFFLINE=1

# 暴露端口
EXPOSE 8080
EXPOSE 9000

# 启动命令
CMD ["python3", "start_telegram_bot.py"]
