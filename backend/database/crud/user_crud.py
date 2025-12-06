"""
用户相关CRUD操作
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from backend.database.models import User, UserInteraction, UserReview


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password_hash: str
) -> User:
    """
    创建用户
    
    Args:
        db: 数据库会话
        username: 用户名
        email: 邮箱
        password_hash: 密码哈希
        
    Returns:
        创建的用户对象
    """
    user = User(
        username=username,
        email=email,
        password_hash=password_hash
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return user


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    根据ID获取用户
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        用户对象或None
    """
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """
    根据用户名获取用户
    
    Args:
        db: 数据库会话
        username: 用户名
        
    Returns:
        用户对象或None
    """
    result = await db.execute(
        select(User).where(User.username == username)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """
    根据邮箱获取用户
    
    Args:
        db: 数据库会话
        email: 邮箱
        
    Returns:
        用户对象或None
    """
    result = await db.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()


async def get_user_interaction_count(db: AsyncSession, user_id: int) -> int:
    """
    获取用户交互次数
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        交互次数
    """
    result = await db.execute(
        select(func.count(UserInteraction.interaction_id))
        .where(UserInteraction.user_id == user_id)
    )
    return result.scalar() or 0


async def get_user_interactions(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[UserInteraction]:
    """
    获取用户交互记录
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        limit: 限制数量
        offset: 偏移量
        
    Returns:
        交互记录列表
    """
    result = await db.execute(
        select(UserInteraction)
        .where(UserInteraction.user_id == user_id)
        .order_by(UserInteraction.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


async def get_user_recent_interactions(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[int]:
    """
    获取用户最近的交互游戏ID列表
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        limit: 限制数量
        
    Returns:
        游戏ID列表
    """
    result = await db.execute(
        select(UserInteraction.product_id)
        .where(UserInteraction.user_id == user_id)
        .order_by(UserInteraction.timestamp.desc())
        .limit(limit)
    )
    return [row[0] for row in result.fetchall()]


async def create_user_interaction(
    db: AsyncSession,
    user_id: int,
    product_id: int,
    timestamp: int,
    play_hours: float = 0.0,
    early_access: bool = False
) -> UserInteraction:
    """
    创建用户交互记录
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        product_id: 游戏ID
        timestamp: 时间戳
        play_hours: 游玩时长
        early_access: 是否抢先体验
        
    Returns:
        交互记录对象
    """
    interaction = UserInteraction(
        user_id=user_id,
        product_id=product_id,
        timestamp=timestamp,
        play_hours=play_hours,
        early_access=early_access
    )
    
    db.add(interaction)
    await db.commit()
    await db.refresh(interaction)
    
    return interaction


async def get_user_played_games(db: AsyncSession, user_id: int) -> List[int]:
    """
    获取用户已玩游戏ID列表
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        已玩游戏ID列表
    """
    result = await db.execute(
        select(UserInteraction.product_id.distinct())
        .where(UserInteraction.user_id == user_id)
    )
    return [row[0] for row in result.fetchall()]


async def create_user_review(
    db: AsyncSession,
    user_id: int,
    product_id: int,
    rating: float,
    review_text: Optional[str] = None
) -> UserReview:
    """
    创建用户评价
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        product_id: 游戏ID
        rating: 评分
        review_text: 评价文本
        
    Returns:
        评价对象
    """
    review = UserReview(
        user_id=user_id,
        product_id=product_id,
        rating=rating,
        review_text=review_text
    )
    
    db.add(review)
    await db.commit()
    await db.refresh(review)
    
    return review


async def get_user_review(
    db: AsyncSession,
    user_id: int,
    product_id: int
) -> Optional[UserReview]:
    """
    获取用户对特定游戏的评价
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        product_id: 游戏ID
        
    Returns:
        评价对象或None
    """
    result = await db.execute(
        select(UserReview)
        .where(
            and_(
                UserReview.user_id == user_id,
                UserReview.product_id == product_id
            )
        )
    )
    return result.scalar_one_or_none()


async def update_user_profile(
    db: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    email: Optional[str] = None
) -> Optional[User]:
    """
    更新用户资料
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        username: 新用户名
        email: 新邮箱
        
    Returns:
        更新后的用户对象或None
    """
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    
    if username is not None:
        user.username = username
    if email is not None:
        user.email = email
    
    await db.commit()
    await db.refresh(user)
    
    return user
