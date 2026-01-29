FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p temp storage log

# 暴露端口
EXPOSE 8080

# 启动命令
CMD ["python3", "start_telegram_bot.py"]
