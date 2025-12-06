"""
用户认证服务
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from backend.auth.password_utils import hash_password, verify_password
from backend.auth.jwt_handler import create_access_token, create_refresh_token
from backend.database.models import User
from backend.database.crud.user_crud import (
    create_user, 
    get_user_by_username, 
    get_user_by_email,
    get_user_by_id
)
from backend.schemas.auth import UserCreate, UserResponse, TokenResponse


class AuthService:
    """用户认证服务"""
    
    @staticmethod
    async def register(
        db: AsyncSession, 
        user_data: UserCreate
    ) -> UserResponse:
        """
        用户注册
        
        Args:
            db: 数据库会话
            user_data: 用户注册数据
            
        Returns:
            用户响应数据
            
        Raises:
            HTTPException: 用户名或邮箱已存在时抛出
        """
        # 检查用户名是否已存在
        existing_user = await get_user_by_username(db, user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # 检查邮箱是否已存在
        existing_email = await get_user_by_email(db, user_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # 加密密码
        hashed_password = hash_password(user_data.password)
        
        # 创建用户
        user = await create_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password_hash=hashed_password
        )
        
        return UserResponse.from_orm(user)
    
    @staticmethod
    async def login(
        db: AsyncSession, 
        username: str, 
        password: str
    ) -> TokenResponse:
        """
        用户登录
        
        Args:
            db: 数据库会话
            username: 用户名
            password: 密码
            
        Returns:
            令牌响应数据
            
        Raises:
            HTTPException: 认证失败时抛出
        """
        # 获取用户
        user = await get_user_by_username(db, username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        # 验证密码
        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        # 创建访问令牌
        access_token = create_access_token(
            data={"sub": str(user.user_id)}
        )
        
        # 创建刷新令牌
        refresh_token = create_refresh_token(user.user_id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=24 * 3600  # 24小时
        )
    
    @staticmethod
    async def verify_token(db: AsyncSession, user_id: int) -> Optional[User]:
        """
        验证令牌有效性
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            用户对象或None
        """
        return await get_user_by_id(db, user_id)
    
    @staticmethod
    async def refresh_token(
        db: AsyncSession, 
        user_id: int
    ) -> TokenResponse:
        """
        刷新访问令牌
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            新的令牌响应数据
            
        Raises:
            HTTPException: 用户不存在时抛出
        """
        # 验证用户是否存在
        user = await get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 创建新的访问令牌
        access_token = create_access_token(
            data={"sub": str(user.user_id)}
        )
        
        # 创建新的刷新令牌
        refresh_token = create_refresh_token(user.user_id)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=24 * 3600  # 24小时
        )
