"""
交互相关API端点
"""

import time
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user_id, get_optional_current_user_id
from backend.database.connection import get_db_session
from backend.database.crud.user_crud import create_user_interaction, create_user_review, get_user_review
from backend.schemas.recommendations import (
    InteractionData, InteractionResponse, 
    UserReviewCreate, UserReviewResponse, FeedbackData
)
from backend.cache.feature_store import FeatureStore
from backend.cache.cache_manager import CacheManager

router = APIRouter()


@router.post("/interact", response_model=InteractionResponse)
async def record_interaction(
    interaction: InteractionData,
    db: AsyncSession = Depends(get_db_session)
):
    """
    记录用户交互事件
    
    - **user_id**: 用户ID
    - **product_id**: 游戏ID
    - **timestamp**: 时间戳（可选，默认当前时间）
    - **play_hours**: 游玩时长（可选）
    - **early_access**: 是否抢先体验（可选）
    
    用于记录用户与游戏的交互行为，如购买、游玩等
    """
    
    try:
        # 设置默认时间戳
        if interaction.timestamp is None:
            interaction.timestamp = int(time.time())
        
        # 创建交互记录
        db_interaction = await create_user_interaction(
            db=db,
            user_id=interaction.user_id,
            product_id=interaction.product_id,
            timestamp=interaction.timestamp,
            play_hours=interaction.play_hours or 0.0,
            early_access=interaction.early_access or False
        )
        
        # 更新Redis用户序列
        feature_store = FeatureStore()
        await feature_store.update_user_sequence(
            interaction.user_id, 
            interaction.product_id
        )
        
        # 清除用户推荐缓存
        cache_manager = CacheManager()
        await cache_manager.invalidate_user_cache(interaction.user_id)
        
        return InteractionResponse(
            status="success",
            message="Interaction recorded successfully",
            interaction_id=db_interaction.interaction_id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record interaction: {str(e)}"
        )


@router.post("/review", response_model=UserReviewResponse)
async def create_review(
    review: UserReviewCreate,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    创建用户评价
    
    - **product_id**: 游戏ID
    - **rating**: 评分 (0-5)
    - **review_text**: 评价文本（可选）
    
    需要有效的认证令牌
    """
    
    # 验证用户权限（只能为自己创建评价）
    if review.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only create reviews for yourself"
        )
    
    try:
        # 检查是否已有评价
        existing_review = await get_user_review(db, review.user_id, review.product_id)
        if existing_review:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Review already exists for this game"
            )
        
        # 创建评价
        db_review = await create_user_review(
            db=db,
            user_id=review.user_id,
            product_id=review.product_id,
            rating=review.rating,
            review_text=review.review_text
        )
        
        return UserReviewResponse(
            review_id=db_review.review_id,
            user_id=db_review.user_id,
            product_id=db_review.product_id,
            rating=db_review.rating,
            review_text=db_review.review_text,
            created_at=db_review.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create review: {str(e)}"
        )


@router.get("/review/{product_id}")
async def get_user_review_endpoint(
    product_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取用户对特定游戏的评价
    
    - **product_id**: 游戏ID
    
    需要有效的认证令牌
    """
    
    try:
        review = await get_user_review(db, current_user_id, product_id)
        
        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review not found"
            )
        
        return UserReviewResponse(
            review_id=review.review_id,
            user_id=review.user_id,
            product_id=review.product_id,
            rating=review.rating,
            review_text=review.review_text,
            created_at=review.created_at.isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get review: {str(e)}"
        )


@router.post("/feedback")
async def record_feedback(
    feedback: FeedbackData,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    记录用户反馈
    
    - **product_id**: 游戏ID
    - **feedback_type**: 反馈类型 (like, dislike, not_interested)
    - **recommendation_id**: 推荐批次ID（可选）
    
    用于收集用户对推荐结果的反馈
    """
    
    # 验证用户权限
    if feedback.user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only create feedback for yourself"
        )
    
    try:
        # 这里应该将反馈存储到数据库
        # 简化处理，实际应该有专门的反馈表
        
        # 记录反馈日志
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"User feedback: user_id={feedback.user_id}, "
            f"product_id={feedback.product_id}, type={feedback.feedback_type}"
        )
        
        # 根据反馈类型调整推荐策略
        if feedback.feedback_type == "dislike":
            # 可以将该游戏加入用户的负反馈列表
            pass
        elif feedback.feedback_type == "like":
            # 可以增强相似游戏的推荐权重
            pass
        elif feedback.feedback_type == "not_interested":
            # 可以降低相似类型游戏的推荐概率
            pass
        
        return {
            "status": "success",
            "message": "Feedback recorded successfully",
            "feedback_type": feedback.feedback_type
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record feedback: {str(e)}"
        )


@router.get("/history")
async def get_interaction_history(
    limit: int = 20,
    current_user_id: int = Depends(get_current_user_id)
):
    """
    获取用户最近的交互历史
    
    - **limit**: 限制数量 (默认20)
    
    返回用户最近的游戏交互记录
    """
    
    try:
        feature_store = FeatureStore()
        
        # 获取用户序列
        user_sequence = await feature_store.get_user_sequence(current_user_id, limit)
        
        if not user_sequence:
            return {
                "user_id": current_user_id,
                "history": [],
                "total": 0,
                "message": "No interaction history found"
            }
        
        # 构造历史记录
        history = []
        for i, product_id in enumerate(user_sequence):
            history.append({
                "product_id": product_id,
                "position": i + 1,  # 在序列中的位置
                "title": f"Game {product_id}",  # 实际应该从数据库获取
                "interaction_type": "play"  # 简化处理
            })
        
        return {
            "user_id": current_user_id,
            "history": history,
            "total": len(history)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get interaction history: {str(e)}"
        )


@router.delete("/history")
async def clear_interaction_history(
    current_user_id: int = Depends(get_current_user_id)
):
    """
    清除用户交互历史
    
    ⚠️ 危险操作：将清除用户的推荐历史数据
    """
    
    try:
        feature_store = FeatureStore()
        cache_manager = CacheManager()
        
        # 清除Redis中的用户序列
        from backend.cache.redis_client import RedisKeyManager
        key_manager = RedisKeyManager()
        
        user_seq_key = key_manager.user_sequence_key(current_user_id)
        await cache_manager.delete_cache(user_seq_key)
        
        # 清除推荐缓存
        await cache_manager.invalidate_user_cache(current_user_id)
        
        return {
            "status": "success",
            "message": "Interaction history cleared successfully",
            "user_id": current_user_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear interaction history: {str(e)}"
        )


@router.get("/stats")
async def get_interaction_stats(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取用户交互统计信息
    
    返回用户的交互数据统计
    """
    
    try:
        from backend.database.crud.user_crud import get_user_interaction_count
        
        # 获取交互次数
        interaction_count = await get_user_interaction_count(db, current_user_id)
        
        # 获取最近活动
        feature_store = FeatureStore()
        recent_games = await feature_store.get_user_sequence(current_user_id, 5)
        
        return {
            "user_id": current_user_id,
            "total_interactions": interaction_count,
            "recent_games": recent_games,
            "recent_activity_count": len(recent_games),
            "user_level": "active" if interaction_count >= 10 else "new" if interaction_count >= 3 else "cold"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get interaction stats: {str(e)}"
        )
