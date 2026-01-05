"""
FastAPI 主应用程序
MisaCard 管理系统 - Python 重构版
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import os

from .database import engine
from . import models
from .api import cards, imports, auth
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="MisaCard 管理系统",
    description="卡片管理系统 - 支持卡片查询、激活、批量导入",
    version="2.0.0"
)


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

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(auth.router, prefix="/api")
app.include_router(cards.router, prefix="/api")
app.include_router(imports.router, prefix="/api")

# 静态文件和模板配置
templates_path = os.path.join(os.path.dirname(__file__), "templates")
static_path = os.path.join(os.path.dirname(__file__), "static")

# 确保目录存在
os.makedirs(static_path, exist_ok=True)

templates = Jinja2Templates(directory=templates_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
async def root(request: Request):
    """激活页面"""
    return templates.TemplateResponse("activate.html", {"request": request}, media_type="text/html")


@app.get("/mobile")
async def mobile(request: Request):
    """移动端页面"""
    return templates.TemplateResponse("mobile.html", {"request": request}, media_type="text/html")

@app.get("/admin")
async def activate(request: Request):
    """管理界面"""
    return templates.TemplateResponse("index.html", {"request": request}, media_type="text/html")

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "MisaCard Backend",
        "version": "2.0.0"
    }


@app.get("/api/info")
async def api_info():
    """API 信息"""
    return {
        "name": "MisaCard API",
        "version": "2.0.0",
        "endpoints": {
            "cards": "/api/cards",
            "import": "/api/import",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
