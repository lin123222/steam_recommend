"""
用户画像相关的 CRUD 操作
"""

from typing import Optional, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.database.models import UserProfile, UserLibrary, User
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


async def get_or_create_user_profile(
    db: AsyncSession,
    user_id: int
) -> Optional[UserProfile]:
    """
    获取或创建用户画像
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        用户画像对象
    """
    try:
        # 查找是否存在
        stmt = select(UserProfile).where(UserProfile.user_id == user_id)
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()
        
        if not profile:
            # 创建新的画像
            profile = UserProfile(
                user_id=user_id,
                member_since=datetime.now().date(),
                gamer_dna_stats=json.dumps(_get_default_gamer_dna_stats()),
                favorite_genres=json.dumps([])
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)
        
        return profile
        
    except Exception as e:
        logger.error(f"Error getting/creating user profile: {e}")
        await db.rollback()
        return None


async def calculate_user_stats(
    db: AsyncSession,
    user_id: int
) -> Dict:
    """
    计算用户统计数据
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        统计数据字典
    """
    try:
        # 获取游戏库统计
        stmt = select(
            func.count(UserLibrary.library_id).label('games_owned'),
            func.sum(UserLibrary.playtime_hours).label('total_playtime'),
            func.sum(UserLibrary.purchase_price).label('library_value'),
            func.sum(UserLibrary.achievements_unlocked).label('achievements_unlocked')
        ).where(UserLibrary.user_id == user_id)
        
        result = await db.execute(stmt)
        row = result.one()
        
        # 计算完美游戏数（成就100%）
        perfect_stmt = select(func.count(UserLibrary.library_id)).where(
            UserLibrary.user_id == user_id,
            UserLibrary.achievement_progress == 100
        )
        perfect_result = await db.execute(perfect_stmt)
        perfect_games = perfect_result.scalar()
        
        # 计算平均游戏时长
        avg_session = 0
        if row.games_owned and row.games_owned > 0:
            avg_session = int((row.total_playtime or 0) * 60 / row.games_owned)
        
        return {
            "total_playtime_hours": float(row.total_playtime or 0),
            "games_owned": row.games_owned or 0,
            "library_value": float(row.library_value or 0),
            "achievements_unlocked": row.achievements_unlocked or 0,
            "perfect_games": perfect_games or 0,
            "avg_session_minutes": avg_session
        }
        
    except Exception as e:
        logger.error(f"Error calculating user stats: {e}")
        return {
            "total_playtime_hours": 0.0,
            "games_owned": 0,
            "library_value": 0.0,
            "achievements_unlocked": 0,
            "perfect_games": 0,
            "avg_session_minutes": 0
        }


async def calculate_gamer_dna(
    db: AsyncSession,
    user_id: int
) -> Dict:
    """
    计算用户的 Gamer DNA
    
    基于用户的游戏库和游玩数据计算6维属性
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        Gamer DNA 数据
    """
    try:
        # 这里简化处理，实际应该基于用户的游戏品类、标签、游玩时长等数据计算
        # 可以使用机器学习模型或规则引擎
        
        # 获取用户游戏库的品类分布
        stmt = select(UserLibrary).where(UserLibrary.user_id == user_id)
        result = await db.execute(stmt)
        library_items = result.scalars().all()
        
        # 简化的计算逻辑（实际应该更复杂）
        stats = _get_default_gamer_dna_stats()
        
        # 根据游戏数量和游玩时长调整
        if len(library_items) > 0:
            # 这里可以添加更复杂的计算逻辑
            stats[0]["value"] = min(85, 50 + len(library_items) * 2)  # 策略
            stats[1]["value"] = min(90, 60 + len(library_items))      # 反应
            stats[2]["value"] = min(95, 70 + len(library_items))      # 探索
            stats[3]["value"] = min(60, 30 + len(library_items))      # 社交
            stats[4]["value"] = min(75, 40 + len(library_items) * 2)  # 收集
            stats[5]["value"] = min(80, 50 + len(library_items))      # 竞技
        
        # 确定主要和次要类型
        primary_type, secondary_type = _determine_player_types(stats)
        
        return {
            "description": "你的游戏基因分析",
            "stats": stats,
            "primary_type": primary_type,
            "secondary_type": secondary_type
        }
        
    except Exception as e:
        logger.error(f"Error calculating gamer DNA: {e}")
        return {
            "description": "你的游戏基因分析",
            "stats": _get_default_gamer_dna_stats(),
            "primary_type": "探索者",
            "secondary_type": "策略家"
        }


def _get_default_gamer_dna_stats() -> List[Dict]:
    """获取默认的 Gamer DNA 统计"""
    return [
        {"name": "策略", "value": 50, "max": 100},
        {"name": "反应", "value": 50, "max": 100},
        {"name": "探索", "value": 50, "max": 100},
        {"name": "社交", "value": 50, "max": 100},
        {"name": "收集", "value": 50, "max": 100},
        {"name": "竞技", "value": 50, "max": 100}
    ]


def _determine_player_types(stats: List[Dict]) -> tuple:
    """根据统计数据确定玩家类型"""
    # 找出最高的两个属性
    sorted_stats = sorted(stats, key=lambda x: x["value"], reverse=True)
    
    type_mapping = {
        "策略": "策略家",
        "反应": "反应者",
        "探索": "探索者",
        "社交": "社交家",
        "收集": "收藏家",
        "竞技": "竞技者"
    }
    
    primary = type_mapping.get(sorted_stats[0]["name"], "探索者")
    secondary = type_mapping.get(sorted_stats[1]["name"], "策略家")
    
    return primary, secondary


async def get_favorite_genres(
    db: AsyncSession,
    user_id: int
) -> List[str]:
    """
    获取用户喜爱的品类
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        品类列表
    """
    try:
        # 这里简化处理，实际应该基于用户的游戏库和游玩时长统计
        # 返回默认的品类
        return ["RPG", "Action", "Strategy"]
        
    except Exception as e:
        logger.error(f"Error getting favorite genres: {e}")
        return []


async def update_user_profile_stats(
    db: AsyncSession,
    user_id: int
) -> bool:
    """
    更新用户画像统计数据
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        
    Returns:
        是否成功
    """
    try:
        profile = await get_or_create_user_profile(db, user_id)
        if not profile:
            return False
        
        # 计算统计数据
        stats = await calculate_user_stats(db, user_id)
        gamer_dna = await calculate_gamer_dna(db, user_id)
        favorite_genres = await get_favorite_genres(db, user_id)
        
        # 更新画像
        profile.total_playtime_hours = stats["total_playtime_hours"]
        profile.games_owned = stats["games_owned"]
        profile.library_value = stats["library_value"]
        profile.achievements_unlocked = stats["achievements_unlocked"]
        profile.perfect_games = stats["perfect_games"]
        profile.avg_session_minutes = stats["avg_session_minutes"]
        
        profile.gamer_dna_stats = json.dumps(gamer_dna["stats"])
        profile.primary_type = gamer_dna["primary_type"]
        profile.secondary_type = gamer_dna["secondary_type"]
        
        profile.favorite_genres = json.dumps(favorite_genres)
        
        await db.commit()
        return True
        
    except Exception as e:
        logger.error(f"Error updating user profile stats: {e}")
        await db.rollback()
        return False
