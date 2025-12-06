"""
认证相关API端点
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.auth_service import AuthService
from backend.auth.dependencies import get_current_user_id
from backend.auth.jwt_handler import verify_refresh_token
from backend.database.connection import get_db_session
from backend.schemas.auth import (
    UserCreate, UserLogin, UserResponse, 
    TokenResponse, RefreshTokenRequest
)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    用户注册
    
    - **username**: 用户名（3-50字符，仅支持字母、数字、下划线、连字符）
    - **email**: 邮箱地址
    - **password**: 密码（8-128字符）
    """
    return await AuthService.register(db, user_data)


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db_session)
):
    """
    用户登录
    
    - **username**: 用户名
    - **password**: 密码
    
    返回访问令牌和刷新令牌
    """
    return await AuthService.login(db, login_data.username, login_data.password)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    刷新访问令牌
    
    - **refresh_token**: 刷新令牌
    
    返回新的访问令牌和刷新令牌
    """
    try:
        # 验证刷新令牌
        user_id = verify_refresh_token(refresh_data.refresh_token)
        
        # 生成新的令牌
        return await AuthService.refresh_token(db, user_id)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.post("/logout")
async def logout():
    """
    用户登出
    
    注意：由于使用JWT，服务端无法主动使令牌失效。
    客户端应该删除本地存储的令牌。
    """
    return {"message": "Logout successful. Please remove tokens from client storage."}


@router.get("/verify")
async def verify_token(
    db: AsyncSession = Depends(get_db_session),
    user_id: int = Depends(get_current_user_id)
):
    """
    验证令牌有效性
    
    需要在请求头中包含有效的Bearer令牌
    """
    user = await AuthService.verify_token(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return {
        "valid": True,
        "user_id": user.user_id,
        "username": user.username
    }
