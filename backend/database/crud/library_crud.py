"""
用户游戏库相关的 CRUD 操作
"""

from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from backend.database.models import UserLibrary, GameMetadata
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


async def get_user_library(
    db: AsyncSession,
    user_id: int,
    filter_type: str = "all",
    sort_by: str = "recent",
    page: int = 1,
    limit: int = 50
) -> Tuple[List[dict], dict]:
    """
    获取用户游戏库
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        filter_type: 筛选类型 (all/installed/favorites/recent)
        sort_by: 排序方式 (recent/name/playtime)
        page: 页码
        limit: 每页数量
        
    Returns:
        (游戏列表, 统计摘要)
    """
    try:
        # 构建基础查询
        stmt = select(UserLibrary, GameMetadata).join(
            GameMetadata,
            UserLibrary.product_id == GameMetadata.product_id
        ).where(UserLibrary.user_id == user_id)
        
        # 应用筛选
        if filter_type == "installed":
            stmt = stmt.where(UserLibrary.is_installed == True)
        elif filter_type == "favorites":
            stmt = stmt.where(UserLibrary.is_favorite == True)
        elif filter_type == "recent":
            # 最近7天内玩过的游戏
            recent_date = datetime.now() - timedelta(days=7)
            stmt = stmt.where(UserLibrary.last_played_at >= recent_date)
        
        # 应用排序
        if sort_by == "name":
            stmt = stmt.order_by(GameMetadata.app_name.asc())
        elif sort_by == "playtime":
            stmt = stmt.order_by(UserLibrary.playtime_hours.desc())
        else:  # recent (default)
            stmt = stmt.order_by(UserLibrary.last_played_at.desc().nullslast())
        
        # 分页
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)
        
        # 执行查询
        result = await db.execute(stmt)
        rows = result.all()
        
        # 转换为字典列表
        games = []
        for library_item, game_meta in rows:
            # 计算相对时间
            last_played_relative = _calculate_relative_time(library_item.last_played_at)
            
            games.append({
                "app_id": game_meta.app_id,
                "app_name": game_meta.app_name,
                "genres": game_meta.genres.split(",") if game_meta.genres else [],
                "tags": game_meta.tags.split(",") if game_meta.tags else [],
                "playtime_hours": float(library_item.playtime_hours) if library_item.playtime_hours else 0.0,
                "last_played_at": library_item.last_played_at.isoformat() if library_item.last_played_at else None,
                "last_played_relative": last_played_relative,
                "is_installed": library_item.is_installed,
                "is_favorite": library_item.is_favorite,
                "achievement_progress": library_item.achievement_progress,
                "achievements_unlocked": library_item.achievements_unlocked,
                "achievements_total": library_item.achievements_total,
                "purchase_date": str(library_item.purchase_date) if library_item.purchase_date else None,
                "purchase_price": float(library_item.purchase_price) if library_item.purchase_price else None
            })
        
        # 获取统计摘要
        summary = await _get_library_summary(db, user_id)
        
        return games, summary
        
    except Exception as e:
        logger.error(f"Error getting user library: {e}")
        return [], {"total_games": 0, "installed_count": 0, "favorites_count": 0}


async def _get_library_summary(db: AsyncSession, user_id: int) -> dict:
    """获取游戏库统计摘要"""
    try:
        # 总游戏数
        total_stmt = select(func.count(UserLibrary.library_id)).where(UserLibrary.user_id == user_id)
        total_result = await db.execute(total_stmt)
        total_games = total_result.scalar()
        
        # 已安装游戏数
        installed_stmt = select(func.count(UserLibrary.library_id)).where(
            and_(UserLibrary.user_id == user_id, UserLibrary.is_installed == True)
        )
        installed_result = await db.execute(installed_stmt)
        installed_count = installed_result.scalar()
        
        # 收藏游戏数
        favorites_stmt = select(func.count(UserLibrary.library_id)).where(
            and_(UserLibrary.user_id == user_id, UserLibrary.is_favorite == True)
        )
        favorites_result = await db.execute(favorites_stmt)
        favorites_count = favorites_result.scalar()
        
        return {
            "total_games": total_games or 0,
            "installed_count": installed_count or 0,
            "favorites_count": favorites_count or 0
        }
        
    except Exception as e:
        logger.error(f"Error getting library summary: {e}")
        return {"total_games": 0, "installed_count": 0, "favorites_count": 0}


def _calculate_relative_time(last_played_at: Optional[datetime]) -> Optional[str]:
    """计算相对时间描述"""
    if not last_played_at:
        return None
    
    now = datetime.now(last_played_at.tzinfo) if last_played_at.tzinfo else datetime.now()
    delta = now - last_played_at
    
    if delta.days == 0:
        return "今天"
    elif delta.days == 1:
        return "昨天"
    elif delta.days < 7:
        return f"{delta.days}天前"
    elif delta.days < 30:
        weeks = delta.days // 7
        return f"{weeks}周前"
    else:
        months = delta.days // 30
        return f"{months}个月前"


async def toggle_favorite(
    db: AsyncSession,
    user_id: int,
    app_id: str
) -> Tuple[bool, bool]:
    """
    切换游戏收藏状态
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        app_id: Steam App ID
        
    Returns:
        (是否成功, 当前收藏状态)
    """
    try:
        # 先获取 product_id
        game_stmt = select(GameMetadata.product_id).where(GameMetadata.app_id == app_id)
        game_result = await db.execute(game_stmt)
        product_id = game_result.scalar_one_or_none()
        
        if not product_id:
            logger.warning(f"Game not found: {app_id}")
            return False, False
        
        # 查找是否已存在库中
        stmt = select(UserLibrary).where(
            and_(UserLibrary.user_id == user_id, UserLibrary.product_id == product_id)
        )
        result = await db.execute(stmt)
        library_item = result.scalar_one_or_none()
        
        if library_item:
            # 切换收藏状态
            library_item.is_favorite = not library_item.is_favorite
            is_liked = library_item.is_favorite
        else:
            # 创建新的库记录
            library_item = UserLibrary(
                user_id=user_id,
                product_id=product_id,
                app_id=app_id,
                is_favorite=True,
                purchase_date=datetime.now().date()
            )
            db.add(library_item)
            is_liked = True
        
        await db.commit()
        return True, is_liked
        
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        await db.rollback()
        return False, False


async def add_to_library(
    db: AsyncSession,
    user_id: int,
    product_id: int,
    app_id: str,
    **kwargs
) -> bool:
    """
    添加游戏到用户库
    
    Args:
        db: 数据库会话
        user_id: 用户ID
        product_id: 产品ID
        app_id: Steam App ID
        **kwargs: 其他可选参数
        
    Returns:
        是否成功
    """
    try:
        # 检查是否已存在
        stmt = select(UserLibrary).where(
            and_(UserLibrary.user_id == user_id, UserLibrary.product_id == product_id)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info(f"Game already in library: user={user_id}, product={product_id}")
            return True
        
        # 创建新记录
        library_item = UserLibrary(
            user_id=user_id,
            product_id=product_id,
            app_id=app_id,
            **kwargs
        )
        db.add(library_item)
        await db.commit()
        
        return True
        
    except Exception as e:
        logger.error(f"Error adding to library: {e}")
        await db.rollback()
        return False


async def update_playtime(
    db: AsyncSession,
    user_id: int,
    product_id: int,
    playtime_hours: float
) -> bool:
    """更新游玩时长"""
    try:
        stmt = select(UserLibrary).where(
            and_(UserLibrary.user_id == user_id, UserLibrary.product_id == product_id)
        )
        result = await db.execute(stmt)
        library_item = result.scalar_one_or_none()
        
        if library_item:
            library_item.playtime_hours = playtime_hours
            library_item.last_played_at = datetime.now()
            await db.commit()
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error updating playtime: {e}")
        await db.rollback()
        return False
