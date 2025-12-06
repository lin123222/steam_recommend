"""
密码加密工具
"""

from passlib.context import CryptContext

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    加密密码
    
    Args:
        password: 明文密码
        
    Returns:
        加密后的密码哈希
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 加密后的密码哈希
        
    Returns:
        密码是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def need_update(hashed_password: str) -> bool:
    """
    检查密码哈希是否需要更新
    
    Args:
        hashed_password: 密码哈希
        
    Returns:
        是否需要更新
    """
    return pwd_context.needs_update(hashed_password)
