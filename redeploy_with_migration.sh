#!/usr/bin/env bash
set -e

# ==========================================
# 1. 拉取最新代码
# ==========================================
echo "==> 1. 拉取最新代码..."
git pull

# ==========================================
# 2. 数据库迁移脚本
#    创建一个临时的 Python 脚本来给数据库添加 legal_address 字段
# ==========================================
echo "==> 2. 准备数据库迁移脚本..."
cat > migrate_db.py << 'EOF'
import sqlite3
import os
import sys

# 数据库路径：对应 Docker 容器内的路径，或者映射到宿主机的路径
# 注意：在宿主机直接运行时，应该是 ./data/cards.db (根据您的 docker run -v 配置)
DB_PATH = "./data/cards.db"

def add_column():
    if not os.path.exists(DB_PATH):
        print(f"数据库 {DB_PATH} 不存在，跳过迁移 (新部署会自动创建正确结构)")
        return

    print(f"正在检查数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 获取现有字段
        cursor.execute("PRAGMA table_info(cards)")
        columns = [i[1] for i in cursor.fetchall()]
        
        # 检查 legal_address
        if "legal_address" not in columns:
            print("正在添加 'legal_address' 字段...")
            cursor.execute("ALTER TABLE cards ADD COLUMN legal_address TEXT")
            conn.commit()
            print("✅ 字段添加成功！")
        else:
            print("ℹ️ 'legal_address' 字段已存在，无需操作。")
            
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        # 这里不退出程序，以免阻断部署流程，可能是新库还没创建表
    finally:
        conn.close()

if __name__ == "__main__":
    add_column()
EOF

# ==========================================
# 3. 执行数据库迁移
#    直接在宿主机执行（前提是宿主机有 python3），或者等容器启动后在容器内执行
#    这里我们在宿主机直接执行，简单快速（因为数据库文件就在 ./data 目录下）
# ==========================================
echo "==> 3. 正在升级数据库结构..."
if [ -f "./data/cards.db" ]; then
    # 尝试使用宿主机的 python3 运行
    if command -v python3 &> /dev/null; then
        python3 migrate_db.py
    else
        echo "⚠️ 宿主机未安装 python3，将在容器启动后尝试自动迁移..."
    fi
else
    echo "ℹ️ 数据库文件不存在，跳过升级。"
fi

# 清理临时迁移脚本
rm -f migrate_db.py

# ==========================================
# 4. 构建 Docker 镜像
# ==========================================
echo "==> 4. 构建 Docker 镜像..."
docker build -t misacard-manager:latest .

# ==========================================
# 5. 停止并删除旧容器
# ==========================================
echo "==> 5. 停止旧容器..."
docker rm -f misacard-manager 2>/dev/null || true

# ==========================================
# 6. 启动新容器
# ==========================================
echo "==> 6. 启动新容器..."
docker run -d \
  --name misacard-manager \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite:///./data/cards.db \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  misacard-manager:latest

echo "==> 🎉 部署完成！"
