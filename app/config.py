"""
应用配置文件
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# MisaCard API 配置
MISACARD_API_BASE_URL = os.getenv(
    "MISACARD_API_BASE_URL",
    "https://api.misacard.com/api/card"
)

MISACARD_API_TOKEN = os.getenv(
    "MISACARD_API_TOKEN",
    "nuceeDqN@UHDHWcpxTcMzj$pDDPrQSd^Q6EY^@$xqNZyRntxu1bmr2qGnJKuFf%&"
)

# API 请求头
MISACARD_API_HEADERS = {
    "Authorization": f"Bearer {MISACARD_API_TOKEN}",
    "Origin": "https://misacard.com",
    "Referer": "https://misacard.com/",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}

# 激活轮询配置
ACTIVATION_MAX_RETRIES = int(os.getenv("ACTIVATION_MAX_RETRIES", 20))  # 最大重试次数
ACTIVATION_RETRY_DELAY = int(os.getenv("ACTIVATION_RETRY_DELAY", 3))   # 重试间隔（秒）

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cards.db")

# 服务器配置
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# 鉴权配置
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "003717")  # 默认密码
AUTH_TOKEN_EXPIRE_HOURS = int(os.getenv("AUTH_TOKEN_EXPIRE_HOURS", 24))  # Token 过期时间（小时）
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production-abc123")  # JWT 密钥
