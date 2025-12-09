"""
Redis特征存储
"""

import json
import pickle
from typing import List, Dict, Optional, Any, Tuple
import numpy as np
import logging

from backend.cache.redis_client import get_redis_client, RedisKeyManager
from backend.config import settings

logger = logging.getLogger(__name__)


class FeatureStore:
    """Redis特征存储"""
    
    def __init__(self):
        # 使用懒加载，避免在模块导入时初始化 Redis
        self._redis = None
        self.key_manager = RedisKeyManager()
    
    @property
    def redis(self):
        """懒加载 Redis 客户端"""
        if self._redis is None:
            self._redis = get_redis_client()
        return self._redis
    
    async def update_user_sequence(self, user_id: int, product_id: int) -> None:
        """
        更新用户行为序列
        
        Args:
            user_id: 用户ID
            product_id: 游戏ID
        """
        key = self.key_manager.user_sequence_key(user_id)
        
        # 添加到序列头部
        await self.redis.lpush(key, product_id)
        
        # 保持序列长度不超过最大值
        await self.redis.ltrim(key, 0, settings.MAX_SEQUENCE_LENGTH - 1)
        
        # 设置过期时间（30天）
        await self.redis.expire(key, 30 * 24 * 3600)
        
        logger.debug(f"Updated user sequence for user {user_id}, added product {product_id}")
    
    async def get_user_sequence(self, user_id: int, max_len: int = 50) -> List[int]:
        """
        获取用户行为序列
        
        Args:
            user_id: 用户ID
            max_len: 最大长度
            
        Returns:
            游戏ID序列
        """
        key = self.key_manager.user_sequence_key(user_id)
        
        # 获取序列
        sequence = await self.redis.lrange(key, 0, max_len - 1)
        
        # 转换为整数列表
        return [int(item_id) for item_id in sequence]
    
    async def cache_embeddings(
        self, 
        model_name: str, 
        user_embeddings: Optional[Dict[int, np.ndarray]] = None,
        item_embeddings: Optional[Dict[int, np.ndarray]] = None
    ) -> None:
        """
        缓存模型嵌入向量
        
        Args:
            model_name: 模型名称
            user_embeddings: 用户嵌入字典
            item_embeddings: 物品嵌入字典
        """
        # 缓存用户嵌入
        if user_embeddings:
            user_key = self.key_manager.user_embedding_key(model_name)
            
            # 序列化嵌入向量并批量存储
            pipeline = self.redis.pipeline()
            for user_id, embedding in user_embeddings.items():
                embedding_bytes = pickle.dumps(embedding.astype(np.float32))
                pipeline.hset(user_key, user_id, embedding_bytes)
            
            await pipeline.execute()
            logger.info(f"Cached {len(user_embeddings)} user embeddings for model {model_name}")
        
        # 缓存物品嵌入
        if item_embeddings:
            item_key = self.key_manager.item_embedding_key(model_name)
            
            # 序列化嵌入向量并批量存储
            pipeline = self.redis.pipeline()
            for item_id, embedding in item_embeddings.items():
                embedding_bytes = pickle.dumps(embedding.astype(np.float32))
                pipeline.hset(item_key, item_id, embedding_bytes)
            
            await pipeline.execute()
            logger.info(f"Cached {len(item_embeddings)} item embeddings for model {model_name}")
    
    async def get_user_embedding(self, user_id: int, model_name: str = "lightgcn") -> Optional[np.ndarray]:
        """
        获取用户嵌入向量
        
        Args:
            user_id: 用户ID
            model_name: 模型名称
            
        Returns:
            嵌入向量或None
        """
        key = self.key_manager.user_embedding_key(model_name)
        
        embedding_bytes = await self.redis.hget(key, user_id)
        if not embedding_bytes:
            return None
        
        try:
            return pickle.loads(embedding_bytes)
        except Exception as e:
            logger.error(f"Failed to deserialize user embedding for user {user_id}: {e}")
            return None
    
    async def get_item_embedding(self, item_id: int, model_name: str = "lightgcn") -> Optional[np.ndarray]:
        """
        获取物品嵌入向量
        
        Args:
            item_id: 物品ID
            model_name: 模型名称
            
        Returns:
            嵌入向量或None
        """
        key = self.key_manager.item_embedding_key(model_name)
        
        embedding_bytes = await self.redis.hget(key, item_id)
        if not embedding_bytes:
            return None
        
        try:
            return pickle.loads(embedding_bytes)
        except Exception as e:
            logger.error(f"Failed to deserialize item embedding for item {item_id}: {e}")
            return None
    
    async def get_batch_item_embeddings(
        self, 
        item_ids: List[int], 
        model_name: str = "lightgcn"
    ) -> Dict[int, np.ndarray]:
        """
        批量获取物品嵌入向量
        
        Args:
            item_ids: 物品ID列表
            model_name: 模型名称
            
        Returns:
            物品ID到嵌入向量的映射
        """
        key = self.key_manager.item_embedding_key(model_name)
        
        # 批量获取
        embeddings = await self.redis.hmget(key, item_ids)
        
        result = {}
        for item_id, embedding_bytes in zip(item_ids, embeddings):
            if embedding_bytes:
                try:
                    result[item_id] = pickle.loads(embedding_bytes)
                except Exception as e:
                    logger.error(f"Failed to deserialize item embedding for item {item_id}: {e}")
        
        return result
    
    async def update_popular_games(self, game_scores: List[Tuple[int, float]]) -> None:
        """
        更新热门游戏榜单
        
        Args:
            game_scores: (游戏ID, 分数)元组列表
        """
        key = self.key_manager.POPULAR_GAMES
        
        # 清空现有榜单
        await self.redis.delete(key)
        
        # 添加新的榜单
        if game_scores:
            # Redis ZADD 需要 score, member 的顺序
            zadd_data = {}
            for game_id, score in game_scores:
                zadd_data[game_id] = score
            
            await self.redis.zadd(key, zadd_data)
            
            # 设置过期时间（1天）
            await self.redis.expire(key, 24 * 3600)
            
            logger.info(f"Updated popular games list with {len(game_scores)} games")
    
    async def get_popular_games(self, limit: int = 100) -> List[Tuple[int, float]]:
        """
        获取热门游戏榜单
        
        Args:
            limit: 限制数量
            
        Returns:
            (游戏ID, 分数)元组列表
        """
        key = self.key_manager.POPULAR_GAMES
        
        # 获取分数最高的游戏（降序）
        games = await self.redis.zrevrange(key, 0, limit - 1, withscores=True)
        
        return [(int(game_id), float(score)) for game_id, score in games]
    
    async def cache_game_metadata(self, game_id: int, metadata: Dict[str, Any]) -> None:
        """
        缓存游戏元数据
        
        Args:
            game_id: 游戏ID
            metadata: 元数据字典
        """
        key = self.key_manager.game_metadata_key(game_id)
        
        # 序列化元数据
        metadata_json = json.dumps(metadata, ensure_ascii=False)
        
        # 存储并设置过期时间（永久）
        await self.redis.set(key, metadata_json)
        
        logger.debug(f"Cached metadata for game {game_id}")
    
    async def get_game_metadata(self, game_id: int) -> Optional[Dict[str, Any]]:
        """
        获取游戏元数据
        
        Args:
            game_id: 游戏ID
            
        Returns:
            元数据字典或None
        """
        key = self.key_manager.game_metadata_key(game_id)
        
        metadata_json = await self.redis.get(key)
        if not metadata_json:
            return None
        
        try:
            return json.loads(metadata_json)
        except Exception as e:
            logger.error(f"Failed to deserialize game metadata for game {game_id}: {e}")
            return None
    
    async def build_genre_index(self, genre_games: Dict[str, List[int]]) -> None:
        """
        构建类型倒排索引
        
        Args:
            genre_games: 类型到游戏ID列表的映射
        """
        pipeline = self.redis.pipeline()
        
        for genre, game_ids in genre_games.items():
            key = self.key_manager.genre_index_key(genre)
            
            # 清空现有索引
            pipeline.delete(key)
            
            # 添加游戏ID到集合
            if game_ids:
                pipeline.sadd(key, *game_ids)
        
        await pipeline.execute()
        logger.info(f"Built genre index for {len(genre_games)} genres")
    
    async def get_games_by_genre(self, genre: str) -> List[int]:
        """
        根据类型获取游戏ID列表
        
        Args:
            genre: 游戏类型
            
        Returns:
            游戏ID列表
        """
        key = self.key_manager.genre_index_key(genre)
        
        game_ids = await self.redis.smembers(key)
        return [int(game_id) for game_id in game_ids]

    async def get_dynamic_user_embedding(
        self,
        user_id: int,
        model_name: str = "lightgcn",
        min_interactions: int = 3,
        fusion_weight: float = 0.1,
        max_sequence_len: int = 10,
        use_time_decay: bool = True
    ) -> Optional[np.ndarray]:
        """
        获取动态用户向量（融合用户交互历史）
        
        当用户交互次数 >= min_interactions 时，将用户交互过的游戏向量
        与用户原始向量进行加权融合，实现实时推荐调整。
        
        Args:
            user_id: 用户ID
            model_name: 模型名称
            min_interactions: 触发融合的最小交互次数
            fusion_weight: 交互向量的融合权重 (0-1)，原始向量权重为 1-fusion_weight
            max_sequence_len: 用于融合的最大序列长度
            use_time_decay: 是否使用时间衰减（最近交互权重更高）
            
        Returns:
            动态用户向量，如果用户不存在则返回 None
        """
        # 1. 获取原始用户向量
        original_embedding = await self.get_user_embedding(user_id, model_name)
        if original_embedding is None:
            return None
        
        # 2. 获取用户交互序列
        user_sequence = await self.get_user_sequence(user_id, max_sequence_len)
        
        # 交互次数不足，直接返回原始向量
        if len(user_sequence) < min_interactions:
            return original_embedding
        
        # 3. 获取交互游戏的向量
        item_embeddings = await self.get_batch_item_embeddings(user_sequence, model_name)
        
        if not item_embeddings:
            return original_embedding
        
        # 4. 计算交互向量（加权平均）
        valid_embeddings = []
        weights = []
        
        for i, item_id in enumerate(user_sequence):
            if item_id in item_embeddings:
                valid_embeddings.append(item_embeddings[item_id])
                
                if use_time_decay:
                    # 时间衰减：最近的交互权重更高
                    # 使用指数衰减：weight = exp(-decay_rate * position)
                    decay_rate = 0.1
                    weight = np.exp(-decay_rate * i)
                else:
                    weight = 1.0
                weights.append(weight)
        
        if not valid_embeddings:
            return original_embedding
        
        # 归一化权重
        weights = np.array(weights)
        weights = weights / weights.sum()
        
        # 加权平均计算交互向量
        interaction_vector = np.zeros_like(original_embedding)
        for emb, w in zip(valid_embeddings, weights):
            interaction_vector += w * emb
        
        # 5. 融合原始向量和交互向量
        dynamic_embedding = (1 - fusion_weight) * original_embedding + fusion_weight * interaction_vector
        
        # 6. L2 归一化（保持向量模长一致）
        norm = np.linalg.norm(dynamic_embedding)
        if norm > 0:
            dynamic_embedding = dynamic_embedding / norm * np.linalg.norm(original_embedding)
        
        logger.debug(
            f"Generated dynamic embedding for user {user_id}: "
            f"{len(valid_embeddings)} items fused with weight {fusion_weight}"
        )
        
        return dynamic_embedding
