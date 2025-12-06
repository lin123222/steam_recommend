"""
JWT Token处理
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status

from backend.config import settings


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问令牌
    
    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量
        
    Returns:
        JWT访问令牌
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm=settings.JWT_ALGORITHM
    )
    
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """
    验证JWT令牌
    
    Args:
        token: JWT令牌
        
    Returns:
        解码后的数据
        
    Raises:
        HTTPException: 令牌无效时抛出
    """
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def get_user_id_from_token(token: str) -> int:
    """
    从令牌中获取用户ID
    
    Args:
        token: JWT令牌
        
    Returns:
        用户ID
        
    Raises:
        HTTPException: 令牌无效或不包含用户ID时抛出
    """
    payload = verify_token(token)
    user_id = payload.get("sub")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        return int(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_refresh_token(user_id: int) -> str:
    """
    创建刷新令牌
    
    Args:
        user_id: 用户ID
        
    Returns:
        刷新令牌
    """
    data = {
        "sub": str(user_id),
        "type": "refresh"
    }
    
    # 刷新令牌有效期为7天
    expires_delta = timedelta(days=7)
    
    return create_access_token(data, expires_delta)


def verify_refresh_token(token: str) -> int:
    """
    验证刷新令牌
    
    Args:
        token: 刷新令牌
        
    Returns:
        用户ID
        
    Raises:
        HTTPException: 令牌无效时抛出
    """
    payload = verify_token(token)
    
    # 检查令牌类型
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return get_user_id_from_token(token)
