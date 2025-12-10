#!/usr/bin/env bash
set -e

echo "=================================================="
echo "安全部署脚本 - MisaCard Manager"
echo "=================================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${YELLOW}步骤 1/5: 备份数据库${NC}"
echo "==> 创建数据库备份"
BACKUP_FILE="data/cards_backup_$(date +%Y%m%d_%H%M%S).db"
if [ -f "data/cards.db" ]; then
    cp data/cards.db "$BACKUP_FILE"
    echo -e "${GREEN}✓ 数据库已备份到: $BACKUP_FILE${NC}"
else
    echo -e "${YELLOW}! 未找到数据库文件，跳过备份${NC}"
fi

echo ""
echo -e "${YELLOW}步骤 2/5: 拉取最新代码${NC}"
git pull
echo -e "${GREEN}✓ 代码已更新${NC}"

echo ""
echo -e "${YELLOW}步骤 3/5: 运行数据库迁移${NC}"
echo "==> 检查并执行迁移脚本"

# 检查是否需要运行迁移
if [ -f "migrate_add_sold_field.py" ]; then
    echo "==> 找到迁移脚本: migrate_add_sold_field.py"
    
    # 在容器外运行迁移（如果有Python环境）
    if command -v python3 &> /dev/null; then
        echo "==> 使用本地Python运行迁移"
        python3 migrate_add_sold_field.py
        echo -e "${GREEN}✓ 数据库迁移完成${NC}"
    else
        echo -e "${RED}! 本地没有Python环境${NC}"
        echo "==> 将在容器启动后自动运行迁移"
    fi
else
    echo -e "${YELLOW}! 未找到迁移脚本${NC}"
fi

echo ""
echo -e "${YELLOW}步骤 4/5: 重新构建Docker镜像${NC}"
docker build -t misacard-manager:latest .
echo -e "${GREEN}✓ 镜像构建完成${NC}"

echo ""
echo -e "${YELLOW}步骤 5/5: 重启容器${NC}"
echo "==> 停止旧容器"
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

echo -e "${GREEN}✓ 容器已启动${NC}"

echo ""
echo "==> 等待服务启动..."
sleep 3

echo ""
echo "==> 检查容器状态"
if docker ps | grep -q misacard-manager; then
    echo -e "${GREEN}✓ 容器运行正常${NC}"
    echo ""
    echo "==> 查看最新日志:"
    docker logs --tail 20 misacard-manager
else
    echo -e "${RED}✗ 容器启动失败！${NC}"
    echo ""
    echo "==> 错误日志:"
    docker logs misacard-manager
    exit 1
fi

echo ""
echo "=================================================="
echo -e "${GREEN}部署完成！${NC}"
echo "=================================================="
echo ""
echo "访问地址: http://localhost:8000"
echo "备份文件: $BACKUP_FILE"
echo ""
echo "常用命令:"
echo "  查看日志: docker logs -f misacard-manager"
echo "  进入容器: docker exec -it misacard-manager bash"
echo "  重启容器: docker restart misacard-manager"
echo ""

