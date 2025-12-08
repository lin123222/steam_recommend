"""
游戏相关的 API 端点
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import get_db_session
from backend.database.crud import game_crud
from backend.schemas.games import (
    GameDetail,
    GameListItem,
    GameListResponse,
    GenreResponse,
    TagResponse
)
from backend.schemas.common import ResponseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _split_text(value: Optional[str]) -> List[str]:
    """将存储为逗号分隔的字符串转为列表"""
    if not value:
        return []
    return [segment.strip() for segment in value.split(",") if segment.strip()]


@router.get("/{app_id}", response_model=ResponseModel)
async def get_game_detail(
    app_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取单个游戏的详情信息
    
    **路径参数**:
    - **app_id**: Steam App ID
    
    **返回**: 游戏详情
    """
    game = await game_crud.get_game_by_id(db, app_id)
    
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    
    # 转换为响应模型
    # GameMetadata 主要字段：product_id, title, app_name, genres, tags, developer, publisher, metascore, sentiment, release_date, price
    title = game.title or game.app_name or str(game.product_id)
    app_name = game.app_name or title

    game_detail = GameDetail(
        app_id=str(game.product_id),
        app_name=app_name,
        description=getattr(game, "description", None),
        short_description=getattr(game, "short_description", None),
        genres=_split_text(game.genres),
        tags=_split_text(game.tags),
        developer=game.developer,
        publisher=game.publisher,
        release_date=str(game.release_date) if game.release_date else None,
        price=float(game.price) if game.price is not None else 0.0,
        discount_price=float(getattr(game, "discount_price", 0.0)) if getattr(game, "discount_price", None) else None,
        discount_percent=int((1 - getattr(game, "discount_price") / game.price) * 100) if getattr(game, "discount_price", None) and game.price else 0,
        specs=_split_text(getattr(game, "specs", None)),
        languages=_split_text(getattr(game, "languages", None)),
        store_url=f"https://store.steampowered.com/app/{game.product_id}",
        reviews_url=f"https://store.steampowered.com/app/{game.product_id}#reviews",
        early_access=bool(getattr(game, "early_access", False))
    )
    
    return ResponseModel(
        code=200,
        message="success",
        data=game_detail
    )


@router.get("", response_model=ResponseModel)
async def get_games_list(
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(20, ge=1, le=50, description="每页数量"),
    genre: Optional[str] = Query(None, description="品类筛选"),
    tags: Optional[str] = Query(None, description="标签筛选（逗号分隔）"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    sort_by: str = Query("popular", description="排序方式: popular/newest/price_asc/price_desc/rating"),
    price_min: Optional[float] = Query(None, description="最低价格"),
    price_max: Optional[float] = Query(None, description="最高价格"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取游戏列表（发现页）
    
    **查询参数**:
    - **page**: 页码（默认1）
    - **limit**: 每页数量（默认20，最大50）
    - **genre**: 按品类筛选（如: RPG, Action）
    - **tags**: 按标签筛选（逗号分隔）
    - **search**: 搜索关键词
    - **sort_by**: 排序方式
    - **price_min**: 最低价格
    - **price_max**: 最高价格
    
    **返回**: 游戏列表和分页信息
    """
    games, total = await game_crud.get_games_list(
        db=db,
        page=page,
        limit=limit,
        genre=genre,
        tags=tags,
        search=search,
        sort_by=sort_by,
        price_min=price_min,
        price_max=price_max
    )
    
    # 转换为响应模型
    game_items = []
    for game in games:
        title = game.title or game.app_name or str(game.product_id)
        app_name = game.app_name or title

        game_items.append(GameListItem(
            app_id=str(game.product_id),
            app_name=app_name,
            genres=_split_text(game.genres),
            tags=_split_text(game.tags),
            price=float(game.price) if game.price is not None else 0.0,
            discount_price=float(getattr(game, "discount_price", 0.0)) if getattr(game, "discount_price", None) else None,
            developer=game.developer,
            publisher=game.publisher,
            release_date=str(game.release_date) if game.release_date else None,
            specs=_split_text(getattr(game, "specs", None)),
            early_access=bool(getattr(game, "early_access", False))
        ))
    
    # 构建分页信息
    total_pages = (total + limit - 1) // limit
    has_more = page < total_pages
    
    response_data = GameListResponse(
        games=game_items,
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": total_pages,
            "has_more": has_more
        },
        filters_applied={
            "genre": genre,
            "tags": tags,
            "search": search,
            "sort_by": sort_by,
            "price_min": price_min,
            "price_max": price_max
        }
    )
    
    return ResponseModel(
        code=200,
        message="success",
        data=response_data
    )


@router.get("/genres", response_model=ResponseModel)
async def get_genres(
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取所有可用的游戏品类列表
    
    **返回**: 品类列表及每个品类的游戏数量
    """
    genres = await game_crud.get_all_genres(db)
    
    response_data = GenreResponse(genres=genres)
    
    return ResponseModel(
        code=200,
        message="success",
        data=response_data
    )


@router.get("/tags", response_model=ResponseModel)
async def get_tags(
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取所有可用的游戏标签列表
    
    **返回**: 标签列表及每个标签的游戏数量（前50个最热门）
    """
    tags = await game_crud.get_all_tags(db)
    
    response_data = TagResponse(tags=tags)
    
    return ResponseModel(
        code=200,
        message="success",
        data=response_data
    )
