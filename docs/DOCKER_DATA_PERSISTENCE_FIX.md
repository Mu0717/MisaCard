# Docker 数据持久化修复指南

## 问题描述

在使用 Docker 部署 MisaCard 管理系统时，每次重启容器后数据会丢失。

### 根本原因

**数据库路径配置不一致**导致的问题：

1. **镜像构建时**（旧版 Dockerfile 第37行）：
   - 执行 `RUN python init_db.py init`
   - 由于构建时没有设置 `DATABASE_URL` 环境变量
   - 数据库被创建在默认路径：`/app/cards.db`（容器内部，未挂载）

2. **容器运行时**（docker-compose.yml 第23行）：
   - 设置环境变量：`DATABASE_URL=sqlite:///./data/cards.db`
   - 挂载 volume：`./data:/app/data`
   - 应用实际使用的是：`/app/data/cards.db`

3. **结果**：
   - 初始化的数据库和运行时使用的数据库路径不同
   - 容器重启后，`/app/cards.db` 丢失，`/app/data/cards.db` 不存在
   - 数据无法持久化

---

## 解决方案

### 方案概述

1. **修改 Dockerfile**：移除镜像构建时的数据库初始化
2. **修改 app/main.py**：在应用启动时自动初始化数据库
3. **在服务器上**：创建 data 目录并重新部署

### 已完成的代码修改

#### 1. Dockerfile 修改

**修改内容**：删除镜像构建时的数据库初始化步骤

```dockerfile
# 创建数据目录（用于持久化数据库）
RUN mkdir -p /app/data

# 注意：数据库将在应用首次启动时自动初始化
# 不在镜像构建时初始化，避免数据库文件路径不匹配导致数据丢失

# 暴露端口
EXPOSE 8000
```

#### 2. app/main.py 修改

**修改内容**：添加启动事件处理器，在应用启动时自动初始化数据库

```python
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    try:
        logger.info("正在初始化数据库...")
        models.Base.metadata.create_all(bind=engine)
        logger.info("✅ 数据库初始化成功")
    except Exception as e:
        logger.error(f"❌ 数据库初始化失败: {e}")
        raise
```

---

## 服务器部署步骤

### 第一步：备份现有数据（如果有）

```bash
# SSH 登录服务器
ssh user@your-server

# 进入项目目录
cd /path/to/MisaCard-Manager-main

# 备份现有数据库（如果存在）
if [ -f cards.db ]; then
    cp cards.db cards.db.backup
    echo "已备份 cards.db 到 cards.db.backup"
fi
```

### 第二步：拉取最新代码

```bash
# 拉取包含修复的最新代码
git pull origin main

# 或者手动上传修改后的文件：
# - Dockerfile
# - app/main.py
```

### 第三步：创建 data 目录

```bash
# 创建数据目录
mkdir -p data

# 设置权限
chmod 755 data

# 如果有旧的数据库文件，移动到 data 目录
if [ -f cards.db ]; then
    mv cards.db data/cards.db
    echo "已移动 cards.db 到 data/cards.db"
fi
```

### 第四步：停止并删除旧容器

```bash
# 如果使用 docker-compose
docker-compose down

# 如果使用 docker run（通过 redeploy.sh）
docker stop misacard-manager 2>/dev/null || true
docker rm misacard-manager 2>/dev/null || true
```

### 第五步：清理旧镜像（可选但推荐）

```bash
# 删除旧的镜像，确保使用新版本
docker rmi misacard-manager:latest 2>/dev/null || true

# 清理无用的构建缓存
docker builder prune -f
```

### 第六步：重新构建并启动

#### 方式 A：使用 docker-compose（推荐）

```bash
# 重新构建镜像（不使用缓存）
docker-compose build --no-cache

# 启动服务
docker-compose up -d

# 查看日志确认启动成功
docker-compose logs -f
```

#### 方式 B：使用 redeploy.sh 脚本

```bash
# 运行重部署脚本
./redeploy.sh

# 查看日志
docker logs -f misacard-manager
```

#### 方式 C：手动 docker run

```bash
# 构建镜像
docker build -t misacard-manager:latest .

# 运行容器
docker run -d \
  --name misacard-manager \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite:///./data/cards.db \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  misacard-manager:latest
```

### 第七步：验证数据持久化

```bash
# 1. 检查 data 目录
ls -lh data/
# 应该看到 cards.db 文件

# 2. 查看容器内的数据库文件
docker exec misacard-manager ls -lh /app/data/
# 应该看到 cards.db 文件

# 3. 检查数据库是否可以读写
docker exec misacard-manager python -c "
from app.database import engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f'数据库表: {tables}')
"

# 4. 访问应用确认正常工作
curl http://localhost:8000/health

# 5. 测试数据持久化：重启容器
docker restart misacard-manager

# 等待几秒后检查数据是否还在
sleep 5
docker exec misacard-manager python -c "
from app.database import SessionLocal
from app.models import Card
db = SessionLocal()
count = db.query(Card).count()
print(f'卡片数量: {count}')
db.close()
"
```

---

## 目录结构说明

### 正确的项目结构

```
MisaCard-Manager-main/          ← 项目根目录（宿主机）
├── app/                         ← 应用代码
│   ├── api/
│   ├── templates/
│   ├── main.py
│   └── ...
├── data/                        ← ⭐ 数据持久化目录
│   └── cards.db                 ← SQLite 数据库文件
├── docs/                        ← 文档目录
├── docker-compose.yml           ← Docker Compose 配置
├── Dockerfile                   ← Docker 镜像构建文件
├── redeploy.sh                  ← 快速重部署脚本
└── requirements.txt             ← Python 依赖
```

### Volume 挂载说明

**docker-compose.yml**：
```yaml
volumes:
  - ./data:/app/data
```

**含义**：
- `./data` → 宿主机的 `项目根目录/data`
- `/app/data` → 容器内的 `/app/data`
- 数据库路径：`/app/data/cards.db`
- 实际存储位置：宿主机的 `项目根目录/data/cards.db`

**效果**：
- 容器内对 `/app/data/cards.db` 的所有操作
- 实际上都在修改宿主机的 `项目根目录/data/cards.db`
- 容器删除、重启后，数据依然保存在宿主机硬盘上

---

## 常见问题排查

### Q1: 重启容器后数据依然丢失

**检查项**：

1. **确认 data 目录存在且挂载成功**：
```bash
# 宿主机上检查
ls -lh data/

# 容器内检查
docker exec misacard-manager ls -lh /app/data/
```

2. **确认环境变量正确**：
```bash
docker exec misacard-manager env | grep DATABASE_URL
# 应该输出：DATABASE_URL=sqlite:///./data/cards.db
```

3. **查看应用日志**：
```bash
docker logs misacard-manager | grep -i database
# 应该看到 "✅ 数据库初始化成功"
```

### Q2: 权限问题

如果遇到权限错误：

```bash
# 检查目录权限
ls -ld data/

# 修改权限
chmod 755 data
chmod 644 data/cards.db

# 如果还有问题，检查 SELinux（CentOS/RHEL）
getenforce
# 如果输出 Enforcing，可能需要：
chcon -Rt svirt_sandbox_file_t data/
```

### Q3: 数据库文件不存在

如果 `data/cards.db` 不存在：

```bash
# 进入容器手动初始化
docker exec -it misacard-manager bash

# 在容器内执行
python init_db.py init

# 或者重启容器（会自动初始化）
docker restart misacard-manager
```

### Q4: 如何迁移现有数据

如果在修复前已有数据：

```bash
# 找到旧数据库位置
docker exec misacard-manager find /app -name "cards.db"

# 复制到正确位置
docker exec misacard-manager cp /app/cards.db /app/data/cards.db

# 或者停止容器后在宿主机操作
docker cp misacard-manager:/app/cards.db ./data/cards.db
```

---

## 监控和维护

### 定期备份

建议设置定期备份任务：

```bash
# 创建备份脚本
cat > backup_db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
cp /path/to/MisaCard-Manager-main/data/cards.db \
   $BACKUP_DIR/cards_${DATE}.db
# 保留最近30天的备份
find $BACKUP_DIR -name "cards_*.db" -mtime +30 -delete
echo "备份完成: cards_${DATE}.db"
EOF

chmod +x backup_db.sh

# 添加到 crontab（每天凌晨2点备份）
crontab -e
# 添加行：
# 0 2 * * * /path/to/backup_db.sh >> /var/log/db_backup.log 2>&1
```

### 查看容器状态

```bash
# 查看运行状态
docker ps | grep misacard-manager

# 查看资源使用
docker stats misacard-manager --no-stream

# 查看健康状态
docker inspect misacard-manager | grep -A 10 Health
```

### 日志管理

```bash
# 实时查看日志
docker logs -f misacard-manager

# 查看最近100行日志
docker logs --tail 100 misacard-manager

# 限制日志大小（在 docker-compose.yml 中添加）
```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```
```

---

## 总结

### 修复核心要点

1. ✅ **Dockerfile**：不在镜像构建时初始化数据库
2. ✅ **app/main.py**：在应用启动时自动初始化数据库
3. ✅ **服务器操作**：创建 data 目录，挂载 volume
4. ✅ **配置一致性**：确保 DATABASE_URL 指向 `/app/data/cards.db`

### 数据持久化原理

```
应用写入数据
    ↓
容器内：/app/data/cards.db
    ↓（volume 挂载）
宿主机：./data/cards.db
    ↓
保存在物理硬盘上
    ↓
容器重启后数据依然存在
```

### 验证清单

- [ ] data 目录存在且有正确权限
- [ ] cards.db 文件在 data 目录中
- [ ] 容器启动日志显示"数据库初始化成功"
- [ ] 重启容器后数据不丢失
- [ ] 健康检查通过

---

## 相关文档

- [Docker 部署指南](./docker-deploy.md)
- [快速开始](./QUICK_START.md)
- [数据库迁移](../migrate_add_used_field.py)

---

## 技术支持

如果遇到其他问题：

1. 查看容器日志：`docker logs misacard-manager`
2. 检查配置文件：`docker-compose.yml`、`Dockerfile`
3. 验证环境变量：`docker exec misacard-manager env`
4. 查看数据库状态：`docker exec misacard-manager python init_db.py check`

---

**最后更新时间**：2024-12-08  
**文档版本**：1.0

