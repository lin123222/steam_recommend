"""
用户认证服务
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, Request

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
from backend.logging_config import get_logger
from backend.utils.logger import log_auth_event

logger = get_logger(__name__)


class AuthService:
    """用户认证服务"""
    
    @staticmethod
    async def register(
        db: AsyncSession, 
        user_data: UserCreate,
        request: Optional[Request] = None
    ) -> UserResponse:
        """
        用户注册
        
        Args:
            db: 数据库会话
            user_data: 用户注册数据
            request: 请求对象（用于获取IP等信息）
            
        Returns:
            用户响应数据
            
        Raises:
            HTTPException: 用户名或邮箱已存在时抛出
        """
        # 获取客户端IP
        client_ip = None
        if request and request.client:
            client_ip = request.client.host
            if "x-forwarded-for" in request.headers:
                client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        logger.info(f"Registration attempt for username: {user_data.username}, email: {user_data.email}")
        
        # 检查用户名是否已存在
        existing_user = await get_user_by_username(db, user_data.username)
        if existing_user:
            log_auth_event(
                event_type="register",
                username=user_data.username,
                success=False,
                ip=client_ip,
                reason="Username already registered"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )
        
        # 检查邮箱是否已存在
        existing_email = await get_user_by_email(db, user_data.email)
        if existing_email:
            log_auth_event(
                event_type="register",
                username=user_data.username,
                success=False,
                ip=client_ip,
                reason="Email already registered"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        try:
            # 加密密码
            hashed_password = hash_password(user_data.password)
            
            # 创建用户
            user = await create_user(
                db=db,
                username=user_data.username,
                email=user_data.email,
                password_hash=hashed_password
            )
            
            logger.info(f"User registered successfully: user_id={user.user_id}, username={user.username}")
            
            log_auth_event(
                event_type="register",
                user_id=user.user_id,
                username=user.username,
                success=True,
                ip=client_ip
            )
            
            return UserResponse.from_orm(user)
            
        except Exception as e:
            logger.error(f"Registration failed for username {user_data.username}: {str(e)}", exc_info=True)
            log_auth_event(
                event_type="register",
                username=user_data.username,
                success=False,
                ip=client_ip,
                reason=f"Internal error: {str(e)}"
            )
            raise
    
    @staticmethod
    async def login(
        db: AsyncSession, 
        username: str, 
        password: str,
        request: Optional[Request] = None
    ) -> TokenResponse:
        """
        用户登录
        
        Args:
            db: 数据库会话
            username: 用户名
            password: 密码
            request: 请求对象（用于获取IP等信息）
            
        Returns:
            令牌响应数据
            
        Raises:
            HTTPException: 认证失败时抛出
        """
        # 获取客户端IP
        client_ip = None
        if request and request.client:
            client_ip = request.client.host
            if "x-forwarded-for" in request.headers:
                client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        logger.info(f"Login attempt for username: {username}")
        
        # 获取用户
        user = await get_user_by_username(db, username)
        if not user:
            log_auth_event(
                event_type="login",
                username=username,
                success=False,
                ip=client_ip,
                reason="Username not found"
            )
            logger.warning(f"Login failed: username '{username}' not found (IP: {client_ip})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        # 验证密码
        if not verify_password(password, user.password_hash):
            log_auth_event(
                event_type="login",
                user_id=user.user_id,
                username=username,
                success=False,
                ip=client_ip,
                reason="Incorrect password"
            )
            logger.warning(f"Login failed: incorrect password for user_id={user.user_id} (IP: {client_ip})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password"
            )
        
        try:
            # 创建访问令牌
            access_token = create_access_token(
                data={"sub": str(user.user_id)}
            )
            
            # 创建刷新令牌
            refresh_token = create_refresh_token(user.user_id)
            
            logger.info(f"User logged in successfully: user_id={user.user_id}, username={username}")
            
            log_auth_event(
                event_type="login",
                user_id=user.user_id,
                username=username,
                success=True,
                ip=client_ip
            )
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=24 * 3600  # 24小时
            )
            
        except Exception as e:
            logger.error(f"Login failed for user_id={user.user_id}: {str(e)}", exc_info=True)
            log_auth_event(
                event_type="login",
                user_id=user.user_id,
                username=username,
                success=False,
                ip=client_ip,
                reason=f"Internal error: {str(e)}"
            )
            raise
    
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
        user_id: int,
        request: Optional[Request] = None
    ) -> TokenResponse:
        """
        刷新访问令牌
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            request: 请求对象（用于获取IP等信息）
            
        Returns:
            新的令牌响应数据
            
        Raises:
            HTTPException: 用户不存在时抛出
        """
        # 获取客户端IP
        client_ip = None
        if request and request.client:
            client_ip = request.client.host
            if "x-forwarded-for" in request.headers:
                client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        logger.debug(f"Token refresh attempt for user_id: {user_id}")
        
        # 验证用户是否存在
        user = await get_user_by_id(db, user_id)
        if not user:
            log_auth_event(
                event_type="token_refresh",
                user_id=user_id,
                success=False,
                ip=client_ip,
                reason="User not found"
            )
            logger.warning(f"Token refresh failed: user_id={user_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        try:
            # 创建新的访问令牌
            access_token = create_access_token(
                data={"sub": str(user.user_id)}
            )
            
            # 创建新的刷新令牌
            refresh_token = create_refresh_token(user.user_id)
            
            logger.debug(f"Token refreshed successfully for user_id={user_id}")
            
            log_auth_event(
                event_type="token_refresh",
                user_id=user_id,
                username=user.username,
                success=True,
                ip=client_ip
            )
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=24 * 3600  # 24小时
            )
            
        except Exception as e:
            logger.error(f"Token refresh failed for user_id={user_id}: {str(e)}", exc_info=True)
            log_auth_event(
                event_type="token_refresh",
                user_id=user_id,
                success=False,
                ip=client_ip,
                reason=f"Internal error: {str(e)}"
            )
            raise
