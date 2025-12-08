"""
鉴权 API 端点
"""
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from ..utils.auth import verify_password, create_access_token, get_current_user
from ..config import AUTH_TOKEN_EXPIRE_HOURS

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    """登录请求模型"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """登录响应模型"""
    success: bool
    message: str
    access_token: str
    token_type: str = "bearer"
    expires_in_hours: int


class VerifyResponse(BaseModel):
    """验证响应模型"""
    success: bool
    message: str
    authenticated: bool


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    账号密码登录接口
    验证账号和密码并返回访问令牌
    """
    # 验证账号（固定为 admin）
    if request.username != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )
    
    # 验证密码
    if not verify_password(request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账号或密码错误",
        )
    
    # 创建访问令牌
    access_token = create_access_token(
        data={"authenticated": True, "username": request.username}
    )
    
    return {
        "success": True,
        "message": "登录成功",
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in_hours": AUTH_TOKEN_EXPIRE_HOURS
    }


@router.get("/verify", response_model=VerifyResponse)
async def verify_token(current_user: dict = Depends(get_current_user)):
    """
    验证当前 token 是否有效
    需要在请求头中携带 Authorization: Bearer <token>
    """
    return {
        "success": True,
        "message": "Token 有效",
        "authenticated": True
    }


@router.post("/logout", response_model=VerifyResponse)
async def logout():
    """
    登出接口（客户端需要删除本地 token）
    服务端无状态，不需要特殊处理
    """
    return {
        "success": True,
        "message": "登出成功",
        "authenticated": False
    }
