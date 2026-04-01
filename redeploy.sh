#!/usr/bin/env bash
set -e

echo "==> 拉取最新代码部署"
git pull || echo "⚠ 拉取新代码有冲突或失败，将尝试继续部署当前本地版本"

echo "==> 停止应用并清理旧环境"
docker-compose down || true

echo "==> 构建并启动新服务包含全自动 HTTPS 网关支持"
docker-compose up -d --build

echo "==> 部署启动命令分发完毕！"
echo "👉 Caddy HTTPS 自动分发程序已在后端工作，请等待 10 秒左右即可验证证书。"
echo "💡 可选：通过 'docker-compose logs -f' 实时监控状态。"