#!/bin/bash

# Tag and Release Script
# 用法: ./tag-and-release.sh [tag] [branch]
# 默认: ./tag-and-release.sh v0.x.x main

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 参数处理
TAG=${1:-$(date +"v0.%Y.%m%d")}
BRANCH=${2:-main}

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   Tag and Release Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 显示配置
echo -e "${YELLOW}配置信息:${NC}"
echo "  分支: $BRANCH"
echo "  标签: $TAG"
echo ""

# 确认操作
read -p "$(echo -e ${YELLOW}确认继续? [y/N] ${NC})" -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}已取消${NC}"
    exit 0
fi

# 切换到指定分支
echo -e "\n${GREEN}[1/4] 切换到分支: $BRANCH${NC}"
git checkout "$BRANCH" || {
    echo -e "${RED}切换分支失败${NC}"
    exit 1
}

# 拉取最新代码
echo -e "${GREEN}[2/4] 拉取最新代码${NC}"
git pull origin "$BRANCH" || {
    echo -e "${RED}拉取代码失败${NC}"
    exit 1
}

# 检查标签是否已存在
if git rev-parse "$TAG" >/dev/null 2>&1; then
    echo -e "${YELLOW}警告: 标签 $TAG 已存在${NC}"
    read -p "$(echo -e ${YELLOW}是否删除旧标签并继续? [y/N] ${NC})" -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        git tag -d "$TAG"
        git push origin ":refs/tags/$TAG" 2>/dev/null || true
        echo -e "${YELLOW}已删除旧标签${NC}"
    else
        echo -e "${RED}已取消${NC}"
        exit 0
    fi
fi

# 创建标签
echo -e "${GREEN}[3/4] 创建标签: $TAG${NC}"
git tag -a "$TAG" -m "Release $TAG" || {
    echo -e "${RED}创建标签失败${NC}"
    exit 1
}

# 推送标签
echo -e "${GREEN}[4/4] 推送标签到远程${NC}"
git push origin "$TAG" || {
    echo -e "${RED}推送标签失败${NC}"
    exit 1
}

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}   发布成功!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "标签: $TAG"
echo "GitHub Actions 将自动构建并推送 Docker 镜像"
echo ""
echo "查看发布页面: https://github.com/$(git remote get-url origin | sed 's|https://github.com/||' | sed 's|.git||')/releases"
echo ""
