"""
认证相关的Pydantic模式
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    """用户注册请求模式"""
    username: str
    email: EmailStr
    password: str
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters long')
        if len(v) > 50:
            raise ValueError('Username must be less than 50 characters')
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, underscores and hyphens')
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if len(v) > 128:
            raise ValueError('Password must be less than 128 characters')
        return v


class UserLogin(BaseModel):
    """用户登录请求模式"""
    username: str
    password: str


class UserResponse(BaseModel):
    """用户响应模式"""
    user_id: int
    username: str
    email: str
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """令牌响应模式"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # 过期时间(秒)


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求模式"""
    refresh_token: str


class UserUpdate(BaseModel):
    """用户更新请求模式"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if v is not None:
            if len(v) < 3:
                raise ValueError('Username must be at least 3 characters long')
            if len(v) > 50:
                raise ValueError('Username must be less than 50 characters')
            if not v.replace('_', '').replace('-', '').isalnum():
                raise ValueError('Username can only contain letters, numbers, underscores and hyphens')
        return v
