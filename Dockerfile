# 使用官方 Python 3.10 镜像作为基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖（排除开发依赖）
# 使用国内 PyPI 镜像，加快依赖安装
RUN pip install --no-cache-dir --upgrade pip \
        -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com && \
    pip install --no-cache-dir -r requirements.txt \
        -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com && \
    pip uninstall -y pytest pytest-asyncio


# 复制应用代码
COPY . .

# 创建数据目录（用于持久化数据库）
RUN mkdir -p /app/data

# 给启动脚本执行权限
RUN chmod +x docker-entrypoint.sh

# 注意：数据库将在应用首次启动时自动初始化
# 不在镜像构建时初始化，避免数据库文件路径不匹配导致数据丢失

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/docs')" || exit 1

# 使用启动脚本（自动处理数据库迁移）
ENTRYPOINT ["/app/docker-entrypoint.sh"]

