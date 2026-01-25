# PKOS Docker 部署指南

本目录包含 PKOS 项目的 Docker 部署配置，支持开发环境和生产环境两种部署方式。

## 目录结构

```
docker/
├── Dockerfile              # Docker 镜像构建文件
├── docker-compose.yml      # 生产环境配置 (使用预构建镜像)
├── docker-compose.dev.yml  # 开发环境配置 (本地代码挂载)
├── .env.example            # 环境变量示例
├── .dockerignore           # Docker 构建忽略文件
└── requirements.txt        # Python 依赖
```

## 快速开始

### 开发环境

开发环境使用本地代码挂载，支持热重载，适合开发调试。

```bash
# 1. 在项目根目录创建 .env 文件 (参考 docker/.env.example)
cp docker/.env.example .env
# 编辑 .env 填写必要的配置

# 2. 启动开发环境
docker-compose -f docker/docker-compose.dev.yml up --build

# 3. 访问应用
# 应用: http://localhost:8080
# 数据库: localhost:5432
# Redis: localhost:6379
```

### 生产环境

生产环境使用预构建的 Docker 镜像，适合线上部署。

```bash
# 1. 准备镜像
# 方式一: 使用 Docker Hub 镜像
export IMAGE_NAME=yourusername/pkos:latest

# 方式二: 使用 GitHub Container Registry 镜像
export IMAGE_NAME=ghcr.io/yourusername/pkos:latest

# 方式三: 使用阿里云镜像
export IMAGE_NAME=registry.cn-hangzhou.aliyuncs.com/yourusername/pkos:latest

# 2. 创建配置文件
cp docker/.env.example docker/.env
# 编辑 docker/.env 填写 IMAGE_NAME 和其他配置

# 3. 启动生产环境
docker-compose -f docker/docker-compose.yml up -d

# 4. 查看日志
docker-compose -f docker/docker-compose.yml logs -f bot
```

## 构建自定义镜像

如果需要自定义镜像（如添加新的依赖），可以手动构建：

```bash
# 在项目根目录执行
docker build -f docker/Dockerfile -t yourusername/pkos:custom .
```

## 环境变量说明

| 变量名 | 说明 | 默认值 | 必需 |
|--------|------|--------|------|
| `IMAGE_NAME` | Docker 镜像名称 | `ghcr.io/yourusername/pkos:latest` | 生产环境必需 |
| `FEISHU_APP_ID` | 飞书应用 ID | - | 是 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | - | 是 |
| `FEISHU_ENCRYPT_KEY` | 飞书加密密钥 | - | 可选 |
| `FEISHU_VERIFICATION_TOKEN` | 飞书验证令牌 | - | 可选 |

### LLM 配置

| 变量名 | 说明 |
|--------|------|
| `LLM_DEFAULT_PROVIDER` | 默认 LLM 提供商 (openai\|deepseek\|glm\|claude) |
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `OPENAI_BASE_URL` | OpenAI API 地址 (默认: https://api.openai.com/v1) |
| `OPENAI_MODEL` | OpenAI 模型 (默认: gpt-4o) |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 (默认: https://api.deepseek.com/v1) |
| `DEEPSEEK_MODEL` | DeepSeek 模型 (默认: deepseek-chat) |
| `GLM_API_KEY` | 智谱 GLM API 密钥 |
| `GLM_BASE_URL` | GLM API 地址 (默认: https://open.bigmodel.cn/api/paas/v4) |
| `GLM_MODEL` | GLM 模型 (默认: glm-4) |
| `CLAUDE_API_KEY` | Claude API 密钥 |
| `CLAUDE_MODEL` | Claude 模型 (默认: claude-3-5-sonnet-20241022) |

## 持久化数据

生产环境通过以下卷挂载实现数据持久化：

| 宿主机目录 | 容器目录 | 说明 |
|------------|----------|------|
| `../config` | `/app/config` | 配置文件 (只读) |
| `../temp` | `/app/temp` | 临时文件 |
| `../logs` | `/app/logs` | 日志文件 |
| `postgres_data` | `/var/lib/postgresql/data` | PostgreSQL 数据 |
| `redis_data` | `/data` | Redis 数据 |

## 常用命令

```bash
# 停止服务
docker-compose -f docker/docker-compose.yml down

# 重启服务
docker-compose -f docker/docker-compose.yml restart

# 查看服务状态
docker-compose -f docker/docker-compose.yml ps

# 查看日志
docker-compose -f docker/docker-compose.yml logs -f [service_name]

# 进入容器
docker-compose -f docker/docker-compose.yml exec bot bash

# 清理所有数据（谨慎使用）
docker-compose -f docker/docker-compose.yml down -v
```

## CI/CD 自动构建

项目配置了 GitHub Actions 自动构建 Docker 镜像，推送 tag 后自动触发：

```bash
# 推送版本标签，自动构建镜像
git tag v1.0.0
git push origin v1.0.0
```

需要在 GitHub 仓库配置以下 Secrets：
- `DOCKER_USERNAME`: Docker Hub 用户名
- `DOCKER_TOKEN`: Docker Hub 访问令牌

## 故障排查

### 镜像拉取失败

检查 `IMAGE_NAME` 配置是否正确，确认镜像是否存在且可访问。

### 端口冲突

修改 `docker-compose.yml` 中的端口映射：
```yaml
ports:
  - "8081:8080"  # 将 8080 改为其他端口
```

### 数据库连接失败

检查数据库环境变量配置，确保 `DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD` 正确。

### 权限问题

确保挂载目录有正确的读写权限：
```bash
chmod -R 755 ../temp ../logs ../config
```
