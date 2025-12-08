# Docker 部署指南

## 📦 部署方式

### 方式一：使用 Docker Compose（推荐）

#### 1. 启动服务

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down

# 重启服务
docker-compose restart
```

#### 2. 访问应用

- **Web 界面**: http://your-server-ip:8000
- **API 文档**: http://your-server-ip:8000/docs

#### 3. 数据持久化

数据库文件会自动保存在 `./data/cards.db`，即使容器重启数据也不会丢失。

### 方式二：使用 Docker 命令

#### 1. 构建镜像

```bash
docker build -t misacard-manager:latest .
```

#### 2. 运行容器

```bash
docker run -d \
  --name misacard-manager \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e TZ=Asia/Shanghai \
  --restart unless-stopped \
  misacard-manager:latest
```

#### 3. 管理容器

```bash
# 查看日志
docker logs -f misacard-manager

# 停止容器
docker stop misacard-manager

# 启动容器
docker start misacard-manager

# 重启容器
docker restart misacard-manager

# 删除容器
docker rm -f misacard-manager
```

## 🔧 配置说明

### 环境变量配置

如果需要自定义配置，可以创建 `.env` 文件：

```env
# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=false

# 数据库配置
DATABASE_URL=sqlite:///./data/cards.db

# 时区设置
TZ=Asia/Shanghai

# MisaCard API（如果需要）
# MISACARD_API_URL=https://api.misacard.com
```

在 `docker-compose.yml` 中取消注释以下行来使用 `.env` 文件：

```yaml
volumes:
  - ./.env:/app/.env
```

### 端口修改

如果 8000 端口被占用，修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "8888:8000"  # 将宿主机端口改为 8888
```

## 📊 常见操作

### 查看容器状态

```bash
docker-compose ps
```

### 进入容器

```bash
docker-compose exec misacard-manager bash
```

### 查看实时日志

```bash
docker-compose logs -f --tail=100
```

### 备份数据库

```bash
# 复制数据库文件到宿主机
cp ./data/cards.db ./cards_backup_$(date +%Y%m%d_%H%M%S).db
```

### 恢复数据库

```bash
# 停止服务
docker-compose down

# 恢复数据库文件
cp cards_backup_20241208_120000.db ./data/cards.db

# 启动服务
docker-compose up -d
```

### 更新应用

```bash
# 停止并删除旧容器
docker-compose down

# 重新构建镜像
docker-compose build --no-cache

# 启动新容器
docker-compose up -d
```

## 🔒 生产环境建议

1. **使用 Nginx 反向代理**

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

2. **配置 HTTPS**

使用 Let's Encrypt 获取免费 SSL 证书：

```bash
certbot --nginx -d your-domain.com
```

3. **定期备份数据**

创建定时任务备份数据库：

```bash
# 添加到 crontab
0 2 * * * cp /path/to/data/cards.db /path/to/backup/cards_$(date +\%Y\%m\%d).db
```

4. **资源限制**

在 `docker-compose.yml` 中添加资源限制：

```yaml
services:
  misacard-manager:
    # ... 其他配置 ...
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

5. **日志管理**

配置日志轮转：

```yaml
services:
  misacard-manager:
    # ... 其他配置 ...
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## 🐛 故障排查

### 容器无法启动

```bash
# 查看详细错误信息
docker-compose logs

# 检查容器状态
docker-compose ps

# 重新构建
docker-compose build --no-cache
docker-compose up -d
```

### 端口冲突

```bash
# 查看端口占用
netstat -tulpn | grep 8000

# 修改 docker-compose.yml 中的端口
```

### 权限问题

```bash
# 确保数据目录有正确的权限
mkdir -p ./data
chmod 755 ./data
```

### 数据库初始化失败

```bash
# 进入容器手动初始化
docker-compose exec misacard-manager python init_db.py init
```

## 📝 注意事项

1. **安全警告**: 此系统未做鉴权，建议仅在局域网内使用或配合防火墙规则限制访问
2. **数据备份**: 定期备份 `./data/cards.db` 文件
3. **更新维护**: 定期更新基础镜像和依赖包以修复安全漏洞
4. **监控日志**: 定期查看应用日志，及时发现问题

## 🎯 快速命令参考

```bash
# 启动
docker-compose up -d

# 停止
docker-compose down

# 重启
docker-compose restart

# 查看日志
docker-compose logs -f

# 更新
docker-compose down && docker-compose build --no-cache && docker-compose up -d

# 备份数据库
cp ./data/cards.db ./backup/cards_$(date +%Y%m%d).db
```

