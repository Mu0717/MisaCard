#!/usr/bin/env bash
set -e

echo "==> 拉取最新代码"
git pull

echo "==> 构建镜像"
docker build -t misacard-manager:latest .

echo "==> 停止并删除旧容器（如有）"
docker rm -f misacard-manager 2>/dev/null || true

echo "==> 启动新容器"
docker run -d \
  --name misacard-manager \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite:///./data/cards.db \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  misacard-manager:latest

echo "==> 完成"