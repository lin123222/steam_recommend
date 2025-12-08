"""
游戏相关的 CRUD 操作
"""

from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, distinct
from sqlalchemy.orm import selectinload
from backend.database.models import GameMetadata
import logging

logger = logging.getLogger(__name__)


async def get_game_by_id(db: AsyncSession, app_id: str) -> Optional[GameMetadata]:
    """
    根据 app_id 获取游戏详情
    
    Args:
        db: 数据库会话
        app_id: Steam App ID
        
    Returns:
        游戏对象或 None
    """
    try:
        # GameMetadata 使用 product_id 作为主键，外部传入的 app_id 兼容为字符串或数字
        try:
            product_id = int(app_id)
        except (TypeError, ValueError):
            logger.error(f"Invalid app_id provided: {app_id}")
            return None

        stmt = select(GameMetadata).where(GameMetadata.product_id == product_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Error getting game {app_id}: {e}")
        return None


async def get_games_by_ids(
    db: AsyncSession,
    product_ids: List[int]
) -> List[GameMetadata]:
    """
    根据一组 product_id 批量获取游戏

    Args:
        db: 数据库会话
        product_ids: 游戏 product_id 列表

    Returns:
        游戏对象列表
    """
    if not product_ids:
        return []

    try:
        stmt = select(GameMetadata).where(GameMetadata.product_id.in_(product_ids))
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        logger.error(f"Error getting games by ids: {e}")
        return []


async def get_games_list(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
    genre: Optional[str] = None,
    tags: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "popular",
    price_min: Optional[float] = None,
    price_max: Optional[float] = None
) -> Tuple[List[GameMetadata], int]:
    """
    获取游戏列表，支持分页、筛选、搜索和排序
    
    Args:
        db: 数据库会话
        page: 页码
        limit: 每页数量
        genre: 品类筛选
        tags: 标签筛选（逗号分隔）
        search: 搜索关键词
        sort_by: 排序方式
        price_min: 最低价格
        price_max: 最高价格
        
    Returns:
        (游戏列表, 总数)
    """
    try:
        # 构建基础查询
        stmt = select(GameMetadata)
        count_stmt = select(func.count(GameMetadata.product_id))
        
        # 筛选条件
        conditions = []
        
        # 品类筛选
        if genre:
            conditions.append(GameMetadata.genres.like(f"%{genre}%"))
        
        # 标签筛选
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            tag_conditions = [GameMetadata.tags.like(f"%{tag}%") for tag in tag_list]
            conditions.append(or_(*tag_conditions))
        
        # 关键词搜索
        if search:
            search_condition = or_(
                GameMetadata.app_name.like(f"%{search}%"),
                GameMetadata.description.like(f"%{search}%")
            )
            conditions.append(search_condition)
        
        # 价格筛选
        if price_min is not None:
            conditions.append(GameMetadata.price >= price_min)
        if price_max is not None:
            conditions.append(GameMetadata.price <= price_max)
        
        # 应用筛选条件
        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))
        
        # 排序
        if sort_by == "newest":
            stmt = stmt.order_by(GameMetadata.release_date.desc())
        elif sort_by == "price_asc":
            stmt = stmt.order_by(GameMetadata.price.asc())
        elif sort_by == "price_desc":
            stmt = stmt.order_by(GameMetadata.price.desc())
        elif sort_by == "rating":
            # 假设有评分字段，如果没有则按热度
            stmt = stmt.order_by(GameMetadata.product_id.desc())
        else:  # popular (default)
            stmt = stmt.order_by(GameMetadata.product_id.desc())
        
        # 分页
        offset = (page - 1) * limit
        stmt = stmt.offset(offset).limit(limit)
        
        # 执行查询
        result = await db.execute(stmt)
        games = result.scalars().all()
        
        # 获取总数
        count_result = await db.execute(count_stmt)
        total = count_result.scalar()
        
        return list(games), total
        
    except Exception as e:
        logger.error(f"Error getting games list: {e}")
        return [], 0


async def get_all_genres(db: AsyncSession) -> List[dict]:
    """
    获取所有品类及其游戏数量
    
    Args:
        db: 数据库会话
        
    Returns:
        品类列表
    """
    try:
        # 获取所有游戏的品类
        stmt = select(GameMetadata.genres).where(GameMetadata.genres.isnot(None))
        result = await db.execute(stmt)
        all_genres_str = result.scalars().all()
        
        # 统计每个品类的数量
        genre_count = {}
        for genres_str in all_genres_str:
            if genres_str:
                # 假设 genres 存储为逗号分隔的字符串
                genres = [g.strip() for g in genres_str.split(",")]
                for genre in genres:
                    if genre:
                        genre_count[genre] = genre_count.get(genre, 0) + 1
        
        # 转换为列表格式
        genres_list = [
            {
                "id": genre.lower().replace(" ", "_"),
                "name": genre,
                "count": count
            }
            for genre, count in sorted(genre_count.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return genres_list
        
    except Exception as e:
        logger.error(f"Error getting genres: {e}")
        return []


async def get_all_tags(db: AsyncSession) -> List[dict]:
    """
    获取所有标签及其游戏数量
    
    Args:
        db: 数据库会话
        
    Returns:
        标签列表
    """
    try:
        # 获取所有游戏的标签
        stmt = select(GameMetadata.tags).where(GameMetadata.tags.isnot(None))
        result = await db.execute(stmt)
        all_tags_str = result.scalars().all()
        
        # 统计每个标签的数量
        tag_count = {}
        for tags_str in all_tags_str:
            if tags_str:
                # 假设 tags 存储为逗号分隔的字符串
                tags = [t.strip() for t in tags_str.split(",")]
                for tag in tags:
                    if tag:
                        tag_count[tag] = tag_count.get(tag, 0) + 1
        
        # 转换为列表格式，只返回前50个最热门的标签
        tags_list = [
            {
                "id": tag.lower().replace(" ", "_"),
                "name": tag,
                "count": count
            }
            for tag, count in sorted(tag_count.items(), key=lambda x: x[1], reverse=True)[:50]
        ]
        
        return tags_list
        
    except Exception as e:
        logger.error(f"Error getting tags: {e}")
        return []


async def search_games(
    db: AsyncSession,
    keyword: str,
    limit: int = 20
) -> List[GameMetadata]:
    """
    搜索游戏
    
    Args:
        db: 数据库会话
        keyword: 搜索关键词
        limit: 返回数量
        
    Returns:
        游戏列表
    """
    try:
        stmt = select(GameMetadata).where(
            or_(
                GameMetadata.app_name.like(f"%{keyword}%"),
                GameMetadata.description.like(f"%{keyword}%"),
                GameMetadata.tags.like(f"%{keyword}%")
            )
        ).limit(limit)
        
        result = await db.execute(stmt)
        return list(result.scalars().all())
        
    except Exception as e:
        logger.error(f"Error searching games: {e}")
        return []
