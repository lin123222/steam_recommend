"""
流行度召回
"""

import time
from typing import List, Tuple, Set
from backend.recall.base_recall import BaseRecall
from backend.cache.feature_store import FeatureStore


class PopularityRecall(BaseRecall):
    """流行度召回器"""
    
    def __init__(self):
        super().__init__("popularity")
        self.feature_store = FeatureStore()
    
    async def recall(
        self, 
        user_id: int, 
        top_k: int = 500,
        exclude_played: bool = True,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        基于流行度的召回
        
        Args:
            user_id: 用户ID
            top_k: 召回数量
            exclude_played: 是否排除已玩游戏
            **kwargs: 其他参数
            
        Returns:
            List[(product_id, score)]: 候选集
        """
        start_time = time.time()
        
        try:
            # 获取热门游戏列表
            popular_games = await self.feature_store.get_popular_games(limit=top_k * 2)
            
            if not popular_games:
                self.logger.warning("No popular games found in cache")
                return []
            
            # 如果需要排除已玩游戏
            if exclude_played:
                # 获取用户已玩游戏（这里简化处理，实际应该从数据库获取）
                played_games = set(await self.feature_store.get_user_sequence(user_id))
                
                # 过滤已玩游戏
                filtered_games = [
                    (game_id, score) for game_id, score in popular_games
                    if game_id not in played_games
                ]
            else:
                filtered_games = popular_games
            
            # 取前top_k个
            candidates = filtered_games[:top_k]
            
            # 记录统计信息
            elapsed_time = time.time() - start_time
            self.log_recall_stats(user_id, len(candidates), elapsed_time)
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"Popularity recall failed for user {user_id}: {e}")
            return []
    
    async def recall_by_genre(
        self,
        user_id: int,
        preferred_genres: List[str],
        top_k: int = 500
    ) -> List[Tuple[int, float]]:
        """
        基于类型偏好的流行度召回
        
        Args:
            user_id: 用户ID
            preferred_genres: 偏好类型列表
            top_k: 召回数量
            
        Returns:
            候选集
        """
        start_time = time.time()
        
        try:
            candidates = []
            
            # 为每个偏好类型获取热门游戏
            for genre in preferred_genres:
                genre_games = await self.feature_store.get_games_by_genre(genre)
                
                if not genre_games:
                    continue
                
                # 获取这些游戏的流行度分数
                popular_games = await self.feature_store.get_popular_games(limit=1000)
                popular_dict = dict(popular_games)
                
                # 筛选该类型的热门游戏
                genre_candidates = [
                    (game_id, popular_dict.get(game_id, 0.0))
                    for game_id in genre_games
                    if game_id in popular_dict
                ]
                
                # 按分数排序
                genre_candidates.sort(key=lambda x: x[1], reverse=True)
                
                # 添加到候选集
                candidates.extend(genre_candidates[:top_k // len(preferred_genres)])
            
            # 去重并按分数排序
            unique_candidates = {}
            for game_id, score in candidates:
                if game_id not in unique_candidates or unique_candidates[game_id] < score:
                    unique_candidates[game_id] = score
            
            # 转换为列表并排序
            final_candidates = list(unique_candidates.items())
            final_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # 取前top_k个
            result = final_candidates[:top_k]
            
            # 记录统计信息
            elapsed_time = time.time() - start_time
            self.log_recall_stats(user_id, len(result), elapsed_time)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Genre-based popularity recall failed for user {user_id}: {e}")
            return []
    
    async def get_trending_games(self, time_window: str = "week") -> List[Tuple[int, float]]:
        """
        获取趋势游戏
        
        Args:
            time_window: 时间窗口（week, month）
            
        Returns:
            趋势游戏列表
        """
        # 这里简化处理，实际应该根据时间窗口计算趋势
        return await self.feature_store.get_popular_games(limit=100)
