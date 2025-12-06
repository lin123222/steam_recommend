"""
用户游戏库相关的 API 端点
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import get_db_session
from backend.database.crud import library_crud
from backend.schemas.library import (
    LibraryResponse,
    LibraryGame,
    LibrarySummary,
    ToggleFavoriteRequest,
    ToggleFavoriteResponse
)
from backend.schemas.common import ResponseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/library", response_model=ResponseModel)
async def get_user_library(
    user_id: str = Query(..., description="用户ID"),
    filter: str = Query("all", description="筛选: all/installed/favorites/recent"),
    sort_by: str = Query("recent", description="排序: recent/name/playtime"),
    page: int = Query(1, ge=1, description="页码"),
    limit: int = Query(50, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取用户游戏库
    
    **查询参数**:
    - **user_id**: 用户ID
    - **filter**: 筛选类型 (all/installed/favorites/recent)
    - **sort_by**: 排序方式 (recent/name/playtime)
    - **page**: 页码
    - **limit**: 每页数量
    
    **返回**: 游戏库列表和统计摘要
    """
    try:
        # 转换 user_id 为整数
        user_id_int = int(user_id) if user_id.isdigit() else hash(user_id) % 1000000
        
        games, summary = await library_crud.get_user_library(
            db=db,
            user_id=user_id_int,
            filter_type=filter,
            sort_by=sort_by,
            page=page,
            limit=limit
        )
        
        # 构建分页信息
        total = summary["total_games"]
        total_pages = (total + limit - 1) // limit
        has_more = page < total_pages
        
        response_data = LibraryResponse(
            games=games,
            summary=LibrarySummary(**summary),
            pagination={
                "page": page,
                "limit": limit,
                "total": total,
                "has_more": has_more
            }
        )
        
        return ResponseModel(
            code=200,
            message="success",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"Error getting user library: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user library")


@router.post("/library/toggle-favorite", response_model=ResponseModel)
async def toggle_favorite(
    request: ToggleFavoriteRequest = Body(...),
    db: AsyncSession = Depends(get_db_session)
):
    """
    切换游戏收藏状态
    
    **请求体**:
    - **user_id**: 用户ID
    - **game_id**: 游戏ID (app_id)
    
    **返回**: 操作结果和当前收藏状态
    """
    try:
        # 转换 user_id 为整数
        user_id_int = int(request.user_id) if request.user_id.isdigit() else hash(request.user_id) % 1000000
        
        success, is_liked = await library_crud.toggle_favorite(
            db=db,
            user_id=user_id_int,
            app_id=request.game_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Game not found")
        
        response_data = ToggleFavoriteResponse(
            success=True,
            is_liked=is_liked,
            message="已添加到收藏" if is_liked else "已取消收藏"
        )
        
        return ResponseModel(
            code=200,
            message="success",
            data=response_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle favorite")


@router.get("/favorites", response_model=ResponseModel)
async def get_favorite_ids(
    user_id: str = Query(..., description="用户ID"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取用户收藏的游戏ID列表
    
    **查询参数**:
    - **user_id**: 用户ID
    
    **返回**: 收藏游戏的ID列表
    """
    try:
        # 转换 user_id 为整数
        user_id_int = int(user_id) if user_id.isdigit() else hash(user_id) % 1000000
        
        # 获取收藏游戏
        games, _ = await library_crud.get_user_library(
            db=db,
            user_id=user_id_int,
            filter_type="favorites",
            sort_by="recent",
            page=1,
            limit=1000  # 获取所有收藏
        )
        
        # 提取游戏ID
        game_ids = [game["app_id"] for game in games]
        
        return ResponseModel(
            code=200,
            message="success",
            data={"games": game_ids}
        )
        
    except Exception as e:
        logger.error(f"Error getting favorite IDs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get favorites")
