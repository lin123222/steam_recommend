"""
推荐相关API端点
"""

import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.pipeline import RecommendationPipeline
from backend.auth.dependencies import get_current_user_id, get_optional_current_user_id
from backend.database.connection import get_db_session
from backend.schemas.recommendations import (
    RecommendationResponse, ExplanationResponse, GameInfo
)
from backend.database.crud.user_crud import get_user_by_id
from backend.database.crud import game_crud

router = APIRouter()

# 全局推荐流程实例（懒加载）
_recommendation_pipeline: Optional[RecommendationPipeline] = None


def get_recommendation_pipeline() -> RecommendationPipeline:
    """获取推荐流程实例（懒加载）"""
    global _recommendation_pipeline
    if _recommendation_pipeline is None:
        _recommendation_pipeline = RecommendationPipeline()
    return _recommendation_pipeline


@router.get("", response_model=RecommendationResponse)
async def get_recommendations(
    user_id: int = Query(..., description="用户ID"),
    topk: int = Query(10, ge=1, le=100, description="推荐数量"),
    algorithm: str = Query("auto", description="推荐算法"),
    ranking_strategy: str = Query("default", description="排序策略"),
    diversity_strength: Optional[float] = Query(None, ge=0.0, le=1.0, description="多样性强度"),
    current_user_id: Optional[int] = Depends(get_optional_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取个性化推荐
    
    - **user_id**: 目标用户ID
    - **topk**: 推荐数量 (1-100)
    - **algorithm**: 推荐算法 (auto, embedding, popularity, content)
    - **ranking_strategy**: 排序策略 (default, diversity_focused, quality_focused)
    - **diversity_strength**: 多样性强度 (0.0-1.0)
    
    支持的算法：
    - auto: 自动选择最适合的算法
    - embedding: 基于用户嵌入的协同过滤
    - popularity: 基于流行度的推荐
    - content: 基于内容的推荐
    
    支持的排序策略：
    - default: 默认平衡策略
    - diversity_focused: 多样性优先策略
    - quality_focused: 质量优先策略
    """
    
    # 验证用户是否存在
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 验证算法参数
    allowed_algorithms = ["auto", "embedding", "popularity", "content"]
    if algorithm not in allowed_algorithms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Algorithm must be one of {allowed_algorithms}"
        )
    
    # 验证排序策略参数
    allowed_strategies = ["default", "diversity_focused", "quality_focused"]
    if ranking_strategy not in allowed_strategies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ranking strategy must be one of {allowed_strategies}"
        )
    
    try:
        # 准备推荐参数
        recommend_kwargs = {}
        if diversity_strength is not None:
            recommend_kwargs["diversity_strength"] = diversity_strength
        
        # 执行推荐流程
        pipeline = get_recommendation_pipeline()
        result = await pipeline.recommend(
            user_id=user_id,
            top_k=topk,
            algorithm=algorithm,
            ranking_strategy=ranking_strategy,
            **recommend_kwargs
        )
        
        # 构造响应数据：批量拉取游戏元数据并保留打分
        scored_recs = result.get("recommendation_scores") or [
            (pid, None) for pid in result.get("recommendations", [])
        ]
        product_ids = [pid for pid, _ in scored_recs]

        games = await game_crud.get_games_by_ids(db, product_ids)
        game_map = {g.product_id: g for g in games}

        def _split_text(value: Optional[str]):
            if not value:
                return []
            return [segment.strip() for segment in value.split(",") if segment.strip()]

        recommendations = []
        for product_id, score in scored_recs:
            meta = game_map.get(product_id)
            title = (meta.title if meta and meta.title else None) \
                or (meta.app_name if meta and meta.app_name else None) \
                or f"Game {product_id}"

            recommendations.append(GameInfo(
                product_id=product_id,
                app_name=meta.app_name if meta else None,
                title=title,
                genres=_split_text(meta.genres) if meta else [],
                tags=_split_text(meta.tags) if meta else [],
                developer=meta.developer if meta else None,
                publisher=meta.publisher if meta else None,
                metascore=meta.metascore if meta else None,
                sentiment=meta.sentiment if meta else None,
                release_date=meta.release_date if meta else None,
                price=meta.price if meta else None,
                discount_price=meta.discount_price if meta else None,
                description=meta.description if meta else None,
                short_description=meta.short_description if meta else None,
                specs=_split_text(meta.specs) if meta and meta.specs else [],
                url=meta.url if meta else None,
                reviews_url=meta.reviews_url if meta else None,
                early_access=meta.early_access if meta else None,
                score=float(score) if score is not None else 0.0
            ))
        
        return RecommendationResponse(
            user_id=user_id,
            recommendations=recommendations,
            algorithm=result["algorithm"],
            timestamp=result["timestamp"],
            total_time_ms=result["total_time_ms"],
            recall_time_ms=result.get("recall_time_ms"),
            ranking_time_ms=result.get("ranking_time_ms")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}"
        )


@router.get("/explanation", response_model=ExplanationResponse)
async def get_recommendation_explanation(
    user_id: int = Query(..., description="用户ID"),
    product_id: int = Query(..., description="游戏ID"),
    current_user_id: Optional[int] = Depends(get_optional_current_user_id),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取推荐解释
    
    - **user_id**: 用户ID
    - **product_id**: 游戏ID
    
    返回为什么推荐这个游戏的解释
    """
    
    # 验证用户是否存在
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        # 获取推荐解释
        pipeline = get_recommendation_pipeline()
        explanation = await pipeline.explain_recommendation(
            user_id=user_id,
            product_id=product_id
        )
        
        return ExplanationResponse(**explanation)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate explanation: {str(e)}"
        )


@router.get("/popular")
async def get_popular_games(
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    genre: Optional[str] = Query(None, description="游戏类型过滤")
):
    """
    获取热门游戏列表
    
    - **limit**: 返回数量 (1-100)
    - **genre**: 可选的游戏类型过滤
    """
    
    try:
        from backend.cache.feature_store import FeatureStore
        feature_store = FeatureStore()
        
        if genre:
            # 获取特定类型的热门游戏
            genre_games = await feature_store.get_games_by_genre(genre)
            popular_games = await feature_store.get_popular_games(limit=1000)
            
            # 筛选该类型的游戏
            popular_dict = dict(popular_games)
            filtered_games = [
                {"product_id": game_id, "score": popular_dict.get(game_id, 0.0)}
                for game_id in genre_games
                if game_id in popular_dict
            ]
            
            # 排序并限制数量
            filtered_games.sort(key=lambda x: x["score"], reverse=True)
            result = filtered_games[:limit]
        else:
            # 获取总体热门游戏
            popular_games = await feature_store.get_popular_games(limit=limit)
            result = [
                {"product_id": game_id, "score": score}
                for game_id, score in popular_games
            ]
        
        return {
            "games": result,
            "genre": genre,
            "total": len(result),
            "timestamp": int(time.time())
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get popular games: {str(e)}"
        )


@router.get("/trending")
async def get_trending_games(
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    time_window: str = Query("week", description="时间窗口")
):
    """
    获取趋势游戏列表
    
    - **limit**: 返回数量 (1-100)
    - **time_window**: 时间窗口 (week, month)
    """
    
    allowed_windows = ["week", "month"]
    if time_window not in allowed_windows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"time_window must be one of {allowed_windows}"
        )
    
    try:
        from backend.recall.popularity_recall import PopularityRecall
        popularity_recall = PopularityRecall()
        
        # 获取趋势游戏
        trending_games = await popularity_recall.get_trending_games(time_window)
        
        result = [
            {"product_id": game_id, "score": score}
            for game_id, score in trending_games[:limit]
        ]
        
        return {
            "games": result,
            "time_window": time_window,
            "total": len(result),
            "timestamp": int(time.time())
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trending games: {str(e)}"
        )


@router.get("/similar/{item_id}")
async def get_similar_games(
    item_id: int,
    limit: int = Query(10, ge=1, le=50, description="返回数量")
):
    """
    获取相似游戏推荐
    
    - **item_id**: 目标游戏ID
    - **limit**: 返回数量 (1-50)
    """
    
    try:
        from backend.recall.embedding_recall import EmbeddingRecall
        embedding_recall = EmbeddingRecall()
        
        # 获取相似游戏
        similar_games = await embedding_recall.recall_similar_items(
            item_id=item_id,
            top_k=limit
        )
        
        result = [
            {"product_id": game_id, "similarity": score}
            for game_id, score in similar_games
        ]
        
        return {
            "target_item_id": item_id,
            "similar_games": result,
            "total": len(result),
            "timestamp": int(time.time())
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get similar games: {str(e)}"
        )


@router.get("/stats")
async def get_recommendation_stats(
    current_user_id: int = Depends(get_current_user_id)
):
    """
    获取推荐系统统计信息（需要认证）
    """
    
    try:
        from backend.cache.cache_manager import CacheManager
        cache_manager = CacheManager()
        
        # 获取缓存统计
        cache_stats = await cache_manager.get_cache_stats()
        
        # 计算缓存命中率
        hits = cache_stats.get("keyspace_hits", 0)
        misses = cache_stats.get("keyspace_misses", 0)
        total_requests = hits + misses
        hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "cache_stats": cache_stats,
            "cache_hit_rate": round(hit_rate, 2),
            "total_cache_requests": total_requests,
            "timestamp": int(time.time())
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recommendation stats: {str(e)}"
        )
