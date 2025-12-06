"""
推荐流程编排
"""

import time
import asyncio
from typing import List, Dict, Tuple, Optional
import logging

from backend.cache.cache_manager import get_cache_manager
from backend.cache.feature_store import FeatureStore
from backend.recall.popularity_recall import PopularityRecall
from backend.recall.embedding_recall import EmbeddingRecall
from backend.ranking.ranking_strategy import RankingStrategy
from backend.database.crud.user_crud import get_user_interaction_count
from backend.database.connection import get_db_session
from backend.config import settings

logger = logging.getLogger(__name__)


class RecommendationPipeline:
    """推荐流程编排器"""
    
    def __init__(self):
        # 使用懒加载，避免在模块导入时初始化 Redis
        self._cache_manager = None
        self._feature_store = None
        self.popularity_recall = PopularityRecall()
        self.embedding_recall = EmbeddingRecall()
        self.ranking_strategy = RankingStrategy()
    
    @property
    def cache_manager(self):
        """懒加载缓存管理器"""
        if self._cache_manager is None:
            self._cache_manager = get_cache_manager()
        return self._cache_manager
    
    @property
    def feature_store(self):
        """懒加载特征存储"""
        if self._feature_store is None:
            self._feature_store = FeatureStore()
        return self._feature_store
    
    async def recommend(
        self, 
        user_id: int, 
        top_k: int = 10,
        algorithm: str = "auto",
        ranking_strategy: str = "default",
        **kwargs
    ) -> Dict:
        """
        端到端推荐流程
        
        Args:
            user_id: 用户ID
            top_k: 返回推荐数量
            algorithm: 指定算法 (auto, embedding, popularity, content)
            ranking_strategy: 排序策略 (default, diversity_focused, quality_focused)
            **kwargs: 其他参数
            
        Returns:
            推荐结果字典
        """
        start_time = time.time()
        
        try:
            # 1. 检查缓存
            if algorithm == "auto":  # 只有自动模式才使用缓存
                cached_recommendations = await self.cache_manager.get_cached_recommendations(user_id)
                if cached_recommendations:
                    total_time = (time.time() - start_time) * 1000
                    logger.info(f"Cache hit for user {user_id}, time: {total_time:.2f}ms")
                    
                    return {
                        "user_id": user_id,
                        "recommendations": cached_recommendations[:top_k],
                        "algorithm": "cached",
                        "timestamp": int(time.time()),
                        "total_time_ms": total_time,
                        "from_cache": True
                    }
            
            # 2. 获取用户交互次数
            interaction_count = await self._get_user_interaction_count(user_id)
            
            # 3. 选择召回策略
            recall_algorithm = self._select_recall_algorithm(algorithm, interaction_count)
            
            # 4. 召回阶段
            recall_start = time.time()
            candidates = await self._recall_stage(user_id, interaction_count, recall_algorithm)
            recall_time = (time.time() - recall_start) * 1000
            
            if not candidates:
                logger.warning(f"No candidates found for user {user_id}")
                return self._empty_recommendation_result(user_id, recall_algorithm)
            
            # 5. 排序和过滤阶段
            ranking_start = time.time()
            filtered_candidates = await self.ranking_strategy.rank_and_filter(
                candidates, user_id, strategy=ranking_strategy, **kwargs
            )
            ranking_time = (time.time() - ranking_start) * 1000
            
            # 7. 获取最终推荐结果
            final_recommendations = filtered_candidates[:top_k]
            
            # 8. 缓存结果（仅自动模式）
            if algorithm == "auto" and final_recommendations:
                recommendation_ids = [item_id for item_id, _ in final_recommendations]
                await self.cache_manager.cache_recommendations(user_id, recommendation_ids)
            
            # 9. 记录推荐日志
            await self._log_recommendation(
                user_id, final_recommendations, recall_algorithm,
                recall_time, ranking_time
            )
            
            total_time = (time.time() - start_time) * 1000
            
            return {
                "user_id": user_id,
                "recommendations": [item_id for item_id, _ in final_recommendations],
                "algorithm": recall_algorithm,
                "timestamp": int(time.time()),
                "total_time_ms": total_time,
                "recall_time_ms": recall_time,
                "ranking_time_ms": ranking_time,
                "from_cache": False
            }
            
        except Exception as e:
            logger.error(f"Recommendation pipeline failed for user {user_id}: {e}")
            return self._empty_recommendation_result(user_id, "error")
    
    async def _get_user_interaction_count(self, user_id: int) -> int:
        """获取用户交互次数"""
        try:
            async with get_db_session() as db:
                return await get_user_interaction_count(db, user_id)
        except Exception as e:
            logger.error(f"Failed to get interaction count for user {user_id}: {e}")
            return 0
    
    def _select_recall_algorithm(self, algorithm: str, interaction_count: int) -> str:
        """选择召回算法"""
        if algorithm != "auto":
            return algorithm
        
        # 自动选择策略
        if interaction_count < settings.MIN_INTERACTION_FOR_CONTENT:
            return "popularity"
        elif interaction_count < settings.MIN_INTERACTION_FOR_EMBEDDING:
            return "content"  # 这里简化为popularity
        else:
            return "embedding"
    
    async def _recall_stage(
        self, 
        user_id: int, 
        interaction_count: int, 
        algorithm: str
    ) -> List[Tuple[int, float]]:
        """召回阶段"""
        recall_size = settings.RECALL_SIZE
        
        if algorithm == "popularity":
            return await self.popularity_recall.recall(user_id, recall_size)
        elif algorithm == "embedding":
            return await self.embedding_recall.recall(user_id, recall_size)
        elif algorithm == "content":
            # 这里简化处理，实际应该实现内容召回
            return await self.popularity_recall.recall(user_id, recall_size)
        else:
            logger.warning(f"Unknown algorithm {algorithm}, fallback to popularity")
            return await self.popularity_recall.recall(user_id, recall_size)
    
    async def _ranking_stage(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int
    ) -> List[Tuple[int, float]]:
        """
        排序阶段 (已弃用，使用RankingStrategy替代)
        
        保留此方法用于向后兼容
        """
        logger.warning("_ranking_stage is deprecated, use RankingStrategy instead")
        
        # 使用新的排序策略
        return await self.ranking_strategy.rank_only(candidates, user_id)
    
    async def _business_filter(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int
    ) -> List[Tuple[int, float]]:
        """
        业务过滤 (已弃用，使用RankingStrategy替代)
        
        保留此方法用于向后兼容
        """
        logger.warning("_business_filter is deprecated, use RankingStrategy instead")
        
        # 使用新的业务过滤器
        return await self.ranking_strategy.filter_only(candidates, user_id)
    
    async def _log_recommendation(
        self,
        user_id: int,
        recommendations: List[Tuple[int, float]],
        algorithm: str,
        recall_time: float,
        ranking_time: float
    ) -> None:
        """记录推荐日志"""
        try:
            # 这里可以记录到数据库或日志系统
            logger.info(
                f"Recommendation completed for user {user_id}: "
                f"algorithm={algorithm}, count={len(recommendations)}, "
                f"recall_time={recall_time:.2f}ms, ranking_time={ranking_time:.2f}ms"
            )
            
            # 可以异步写入数据库
            # await self._save_recommendation_log(...)
            
        except Exception as e:
            logger.error(f"Failed to log recommendation for user {user_id}: {e}")
    
    def _empty_recommendation_result(self, user_id: int, algorithm: str) -> Dict:
        """返回空推荐结果"""
        return {
            "user_id": user_id,
            "recommendations": [],
            "algorithm": algorithm,
            "timestamp": int(time.time()),
            "total_time_ms": 0.0,
            "from_cache": False
        }
    
    async def explain_recommendation(
        self, 
        user_id: int, 
        product_id: int
    ) -> Dict:
        """
        推荐解释
        
        Args:
            user_id: 用户ID
            product_id: 游戏ID
            
        Returns:
            解释结果
        """
        try:
            # 获取用户历史
            user_sequence = await self.feature_store.get_user_sequence(user_id, 10)
            
            if not user_sequence:
                return {
                    "product_id": product_id,
                    "explanation": "基于热门游戏推荐",
                    "influential_games": [],
                    "algorithm": "popularity"
                }
            
            # 简化的解释逻辑
            # 实际应该分析推荐路径、计算影响权重等
            
            explanation = f"基于您最近游玩的游戏历史进行推荐"
            influential_games = [
                {
                    "product_id": game_id,
                    "title": f"Game {game_id}",  # 实际应该从数据库获取
                    "weight": 1.0 / (i + 1)  # 简化的权重计算
                }
                for i, game_id in enumerate(user_sequence[:3])
            ]
            
            return {
                "product_id": product_id,
                "explanation": explanation,
                "influential_games": influential_games,
                "algorithm": "embedding"
            }
            
        except Exception as e:
            logger.error(f"Failed to explain recommendation for user {user_id}, product {product_id}: {e}")
            return {
                "product_id": product_id,
                "explanation": "推荐解释暂不可用",
                "influential_games": [],
                "algorithm": "unknown"
            }
