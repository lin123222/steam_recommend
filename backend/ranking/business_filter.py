"""
业务过滤器
"""

import json
from typing import List, Tuple, Set, Dict, Any
from collections import defaultdict
import logging

from backend.cache.feature_store import FeatureStore
from backend.config import settings

logger = logging.getLogger(__name__)


class BusinessFilter:
    """业务过滤器"""
    
    def __init__(self):
        self.feature_store = FeatureStore()
        
        # 业务规则配置
        self.max_same_developer = settings.MAX_SAME_DEVELOPER  # 同一开发商最大数量
        self.max_same_genre = settings.MAX_SAME_GENRE          # 同一类型最大数量
        
        self.logger = logging.getLogger(__name__)
    
    async def filter(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        应用业务过滤规则
        
        Args:
            candidates: 排序后的候选集
            user_id: 用户ID
            **kwargs: 其他参数
            
        Returns:
            过滤后的候选集
        """
        try:
            if not candidates:
                return candidates
            
            # 1. 过滤用户已玩游戏
            filtered = await self._filter_played_games(candidates, user_id)
            
            # 2. 开发商多样性过滤
            filtered = await self._filter_by_developer_diversity(filtered)
            
            # 3. 类型多样性过滤
            filtered = await self._filter_by_genre_diversity(filtered)
            
            # 4. 价格过滤（可选）
            filtered = await self._filter_by_price(filtered, kwargs.get('price_range'))
            
            # 5. 年龄限制过滤（可选）
            filtered = await self._filter_by_age_rating(filtered, kwargs.get('user_age'))
            
            self.logger.info(
                f"Business filter for user {user_id}: "
                f"{len(candidates)} -> {len(filtered)} candidates"
            )
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"Business filter failed for user {user_id}: {e}")
            return candidates  # 返回原始候选集
    
    async def _filter_played_games(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int
    ) -> List[Tuple[int, float]]:
        """
        过滤用户已玩游戏
        
        Args:
            candidates: 候选集
            user_id: 用户ID
            
        Returns:
            过滤后的候选集
        """
        try:
            # 获取用户已玩游戏
            played_games = set(await self.feature_store.get_user_sequence(user_id))
            
            # 过滤已玩游戏
            filtered = [
                (item_id, score) for item_id, score in candidates
                if item_id not in played_games
            ]
            
            self.logger.debug(
                f"Filtered {len(candidates) - len(filtered)} played games for user {user_id}"
            )
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"Failed to filter played games for user {user_id}: {e}")
            return candidates
    
    async def _filter_by_developer_diversity(
        self, 
        candidates: List[Tuple[int, float]]
    ) -> List[Tuple[int, float]]:
        """
        按开发商多样性过滤
        
        Args:
            candidates: 候选集
            
        Returns:
            过滤后的候选集
        """
        try:
            developer_counts = defaultdict(int)
            filtered = []
            
            for item_id, score in candidates:
                # 获取游戏元数据
                metadata = await self.feature_store.get_game_metadata(item_id)
                
                if not metadata:
                    # 没有元数据，直接添加
                    filtered.append((item_id, score))
                    continue
                
                developer = metadata.get("developer", "Unknown")
                
                # 检查开发商数量限制
                if developer_counts[developer] < self.max_same_developer:
                    filtered.append((item_id, score))
                    developer_counts[developer] += 1
                else:
                    self.logger.debug(
                        f"Filtered game {item_id} due to developer limit: {developer}"
                    )
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"Failed to filter by developer diversity: {e}")
            return candidates
    
    async def _filter_by_genre_diversity(
        self, 
        candidates: List[Tuple[int, float]]
    ) -> List[Tuple[int, float]]:
        """
        按类型多样性过滤
        
        Args:
            candidates: 候选集
            
        Returns:
            过滤后的候选集
        """
        try:
            genre_counts = defaultdict(int)
            filtered = []
            
            for item_id, score in candidates:
                # 获取游戏元数据
                metadata = await self.feature_store.get_game_metadata(item_id)
                
                if not metadata:
                    # 没有元数据，直接添加
                    filtered.append((item_id, score))
                    continue
                
                # 解析游戏类型
                genres = metadata.get("genres", [])
                if isinstance(genres, str):
                    try:
                        genres = json.loads(genres)
                    except:
                        genres = []
                
                # 检查是否超过类型限制
                can_add = True
                for genre in genres:
                    if genre_counts[genre] >= self.max_same_genre:
                        can_add = False
                        break
                
                if can_add:
                    filtered.append((item_id, score))
                    # 更新类型计数
                    for genre in genres:
                        genre_counts[genre] += 1
                else:
                    self.logger.debug(
                        f"Filtered game {item_id} due to genre limit: {genres}"
                    )
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"Failed to filter by genre diversity: {e}")
            return candidates
    
    async def _filter_by_price(
        self, 
        candidates: List[Tuple[int, float]],
        price_range: Tuple[float, float] = None
    ) -> List[Tuple[int, float]]:
        """
        按价格过滤
        
        Args:
            candidates: 候选集
            price_range: 价格范围 (min_price, max_price)
            
        Returns:
            过滤后的候选集
        """
        if not price_range:
            return candidates
        
        try:
            min_price, max_price = price_range
            filtered = []
            
            for item_id, score in candidates:
                # 获取游戏元数据
                metadata = await self.feature_store.get_game_metadata(item_id)
                
                if not metadata:
                    # 没有价格信息，直接添加
                    filtered.append((item_id, score))
                    continue
                
                price = metadata.get("price")
                if price is None:
                    # 没有价格信息，直接添加
                    filtered.append((item_id, score))
                elif min_price <= price <= max_price:
                    filtered.append((item_id, score))
                else:
                    self.logger.debug(
                        f"Filtered game {item_id} due to price: {price} not in [{min_price}, {max_price}]"
                    )
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"Failed to filter by price: {e}")
            return candidates
    
    async def _filter_by_age_rating(
        self, 
        candidates: List[Tuple[int, float]],
        user_age: int = None
    ) -> List[Tuple[int, float]]:
        """
        按年龄限制过滤
        
        Args:
            candidates: 候选集
            user_age: 用户年龄
            
        Returns:
            过滤后的候选集
        """
        if not user_age:
            return candidates
        
        try:
            filtered = []
            
            for item_id, score in candidates:
                # 获取游戏元数据
                metadata = await self.feature_store.get_game_metadata(item_id)
                
                if not metadata:
                    # 没有年龄限制信息，直接添加
                    filtered.append((item_id, score))
                    continue
                
                # 这里简化处理，实际应该有专门的年龄限制字段
                # 可以根据游戏标签或其他信息判断
                tags = metadata.get("tags", [])
                if isinstance(tags, str):
                    try:
                        tags = json.loads(tags)
                    except:
                        tags = []
                
                # 简单的年龄限制判断
                is_mature = any(
                    tag.lower() in ["mature", "adult", "18+", "violence", "gore"]
                    for tag in tags
                )
                
                if is_mature and user_age < 18:
                    self.logger.debug(
                        f"Filtered game {item_id} due to age restriction for user age {user_age}"
                    )
                else:
                    filtered.append((item_id, score))
            
            return filtered
            
        except Exception as e:
            self.logger.error(f"Failed to filter by age rating: {e}")
            return candidates
    
    def update_filter_rules(
        self, 
        max_same_developer: int = None,
        max_same_genre: int = None
    ) -> None:
        """
        更新过滤规则
        
        Args:
            max_same_developer: 同一开发商最大数量
            max_same_genre: 同一类型最大数量
        """
        if max_same_developer is not None:
            self.max_same_developer = max_same_developer
        
        if max_same_genre is not None:
            self.max_same_genre = max_same_genre
        
        self.logger.info(
            f"Updated filter rules: "
            f"max_developer={self.max_same_developer}, "
            f"max_genre={self.max_same_genre}"
        )
