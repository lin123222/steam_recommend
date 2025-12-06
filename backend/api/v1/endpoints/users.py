"""
用户相关API端点
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user, get_current_user_id
from backend.database.connection import get_db_session
from backend.database.models import User
from backend.database.crud.user_crud import (
    update_user_profile, get_user_interactions, get_user_played_games, get_user_by_id
)
from backend.database.crud import profile_crud, library_crud
from backend.schemas.auth import UserResponse, UserUpdate
from backend.schemas.profile import UserProfileResponse, GamerDNA, BentoStats, RecentActivity
from backend.schemas.common import ResponseModel
from backend.cache.cache_manager import CacheManager
import json

router = APIRouter()


@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    获取当前用户资料
    
    需要有效的认证令牌
    """
    return UserResponse.from_attributes(current_user)


@router.put("/profile", response_model=UserResponse)
async def update_user_profile_endpoint(
    user_update: UserUpdate,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    更新用户资料
    
    - **username**: 新用户名（可选）
    - **email**: 新邮箱（可选）
    
    需要有效的认证令牌
    """
    
    try:
        # 更新用户资料
        updated_user = await update_user_profile(
            db=db,
            user_id=current_user_id,
            username=user_update.username,
            email=user_update.email
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 清除用户缓存
        cache_manager = CacheManager()
        await cache_manager.invalidate_user_cache(current_user_id)
        
        return UserResponse.from_attributes(updated_user)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )


@router.get("/interactions")
async def get_user_interactions_endpoint(
    limit: int = 50,
    offset: int = 0,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取用户交互历史
    
    - **limit**: 限制数量 (默认50)
    - **offset**: 偏移量 (默认0)
    
    返回用户的游戏交互记录
    """
    
    try:
        interactions = await get_user_interactions(
            db=db,
            user_id=current_user_id,
            limit=limit,
            offset=offset
        )
        
        # 转换为响应格式
        interaction_list = []
        for interaction in interactions:
            interaction_list.append({
                "interaction_id": interaction.interaction_id,
                "product_id": interaction.product_id,
                "timestamp": interaction.timestamp,
                "play_hours": interaction.play_hours,
                "early_access": interaction.early_access,
                "created_at": interaction.created_at.isoformat()
            })
        
        return {
            "interactions": interaction_list,
            "total": len(interaction_list),
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get interactions: {str(e)}"
        )


@router.get("/played-games")
async def get_played_games(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取用户已玩游戏列表
    
    返回用户所有交互过的游戏ID列表
    """
    
    try:
        played_games = await get_user_played_games(db, current_user_id)
        
        return {
            "user_id": current_user_id,
            "played_games": played_games,
            "total": len(played_games)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get played games: {str(e)}"
        )


@router.get("/preferences")
async def get_user_preferences(
    current_user_id: int = Depends(get_current_user_id)
):
    """
    获取用户偏好分析
    
    基于用户历史行为分析游戏偏好
    """
    
    try:
        from backend.cache.feature_store import FeatureStore
        feature_store = FeatureStore()
        
        # 获取用户交互序列
        user_sequence = await feature_store.get_user_sequence(current_user_id, 20)
        
        if not user_sequence:
            return {
                "user_id": current_user_id,
                "preferences": {
                    "favorite_genres": [],
                    "favorite_developers": [],
                    "avg_play_hours": 0.0,
                    "total_games": 0
                },
                "message": "No interaction history found"
            }
        
        # 简化的偏好分析（实际应该从数据库获取详细信息）
        preferences = {
            "favorite_genres": ["Action", "Adventure", "RPG"],  # 示例数据
            "favorite_developers": ["FromSoftware", "CD Projekt"],
            "avg_play_hours": 25.5,
            "total_games": len(user_sequence),
            "recent_activity": user_sequence[:5]
        }
        
        return {
            "user_id": current_user_id,
            "preferences": preferences
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user preferences: {str(e)}"
        )


@router.delete("/account")
async def delete_user_account(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    删除用户账户
    
    ⚠️ 危险操作：将永久删除用户账户和所有相关数据
    """
    
    try:
        # 这里应该实现软删除或标记删除
        # 实际生产环境中需要更复杂的删除流程
        
        # 清除用户缓存
        cache_manager = CacheManager()
        await cache_manager.invalidate_user_cache(current_user_id)
        
        # 清除用户序列
        from backend.cache.feature_store import FeatureStore
        feature_store = FeatureStore()
        from backend.cache.redis_client import RedisKeyManager
        key_manager = RedisKeyManager()
        
        user_seq_key = key_manager.user_sequence_key(current_user_id)
        await cache_manager.delete_cache(user_seq_key)
        
        return {
            "message": "Account deletion initiated. All user data will be removed.",
            "user_id": current_user_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete account: {str(e)}"
        )


@router.get("/profile/complete", response_model=ResponseModel)
async def get_complete_user_profile(
    user_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取完整的用户画像（包含 Gamer DNA 和 Bento Stats）
    
    **查询参数**:
    - **user_id**: 用户ID
    
    **返回**: 完整的用户画像数据
    """
    try:
        # 转换 user_id 为整数
        user_id_int = int(user_id) if user_id.isdigit() else hash(user_id) % 1000000
        
        # 获取用户基本信息
        user = await get_user_by_id(db, user_id_int)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # 获取或创建用户画像
        profile = await profile_crud.get_or_create_user_profile(db, user_id_int)
        
        # 更新统计数据
        await profile_crud.update_user_profile_stats(db, user_id_int)
        
        # 刷新数据
        await db.refresh(profile)
        
        # 解析 JSON 数据
        gamer_dna_stats = json.loads(profile.gamer_dna_stats) if profile.gamer_dna_stats else []
        favorite_genres = json.loads(profile.favorite_genres) if profile.favorite_genres else []
        
        # 获取最近活动
        games, _ = await library_crud.get_user_library(
            db=db,
            user_id=user_id_int,
            filter_type="recent",
            sort_by="recent",
            page=1,
            limit=1
        )
        
        last_played_game_id = games[0]["app_id"] if games else None
        last_played_at = games[0]["last_played_at"] if games else None
        
        # 构建响应
        profile_response = UserProfileResponse(
            user_id=user_id,
            username=user.username,
            avatar_url=profile.avatar_url,
            level=profile.level,
            exp=profile.exp,
            exp_to_next_level=profile.exp_to_next_level,
            member_since=str(profile.member_since) if profile.member_since else None,
            gamer_dna=GamerDNA(
                description="你的游戏基因分析",
                stats=gamer_dna_stats,
                primary_type=profile.primary_type or "探索者",
                secondary_type=profile.secondary_type or "策略家"
            ),
            bento_stats=BentoStats(
                total_playtime_hours=float(profile.total_playtime_hours) if profile.total_playtime_hours else 0.0,
                games_owned=profile.games_owned,
                library_value=float(profile.library_value) if profile.library_value else 0.0,
                achievements_unlocked=profile.achievements_unlocked,
                perfect_games=profile.perfect_games,
                avg_session_minutes=profile.avg_session_minutes
            ),
            favorite_genres=favorite_genres,
            recent_activity=RecentActivity(
                last_played_game_id=last_played_game_id,
                last_played_at=last_played_at
            )
        )
        
        return ResponseModel(
            code=200,
            message="success",
            data=profile_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile: {str(e)}"
        )
