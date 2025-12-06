"""
FastAPI依赖注入
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.jwt_handler import get_user_id_from_token
from backend.database.connection import get_db_session
from backend.database.crud.user_crud import get_user_by_id
from backend.database.models import User

# HTTP Bearer认证方案
security = HTTPBearer()


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int:
    """
    获取当前用户ID
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        当前用户ID
        
    Raises:
        HTTPException: 认证失败时抛出
    """
    token = credentials.credentials
    return get_user_id_from_token(token)


async def get_current_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
) -> User:
    """
    获取当前用户对象
    
    Args:
        user_id: 用户ID
        db: 数据库会话
        
    Returns:
        用户对象
        
    Raises:
        HTTPException: 用户不存在时抛出
    """
    user = await get_user_by_id(db, user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


async def get_optional_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> int | None:
    """
    获取可选的当前用户ID（用于可选认证的接口）
    
    Args:
        credentials: HTTP认证凭据
        
    Returns:
        用户ID或None
    """
    if not credentials:
        return None
    
    try:
        return get_user_id_from_token(credentials.credentials)
    except HTTPException:
        return None
