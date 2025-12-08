"""
鉴权工具模块
基于 JWT Token 的密码鉴权系统
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..config import AUTH_PASSWORD, AUTH_TOKEN_EXPIRE_HOURS, SECRET_KEY

# JWT 配置
ALGORITHM = "HS256"

# HTTP Bearer Token 方案
security = HTTPBearer(auto_error=False)


def verify_password(password: str) -> bool:
    """
    验证密码是否正确
    
    Args:
        password: 用户输入的密码
        
    Returns:
        True 如果密码正确，否则 False
    """
    return password == AUTH_PASSWORD


def create_access_token(data: dict) -> str:
    """
    创建 JWT 访问令牌
    
    Args:
        data: 要编码到 token 中的数据
        
    Returns:
        JWT token 字符串
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=AUTH_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    验证 JWT token
    
    Args:
        token: JWT token 字符串
        
    Returns:
        解码后的 token 数据，如果验证失败则返回 None
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    获取当前已认证用户（依赖注入）
    用于需要鉴权的端点
    
    Args:
        credentials: HTTP Bearer 认证凭据
        
    Returns:
        用户信息字典
        
    Raises:
        HTTPException: 如果 token 无效或已过期
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return payload


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    获取当前用户（可选）
    不会抛出异常，如果未认证则返回 None
    用于可选鉴权的端点
    
    Args:
        credentials: HTTP Bearer 认证凭据
        
    Returns:
        用户信息字典，如果未认证则返回 None
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    payload = verify_token(token)
    
    return payload
