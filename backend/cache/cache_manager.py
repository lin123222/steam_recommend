"""
缓存管理器
"""

import json
from typing import List, Optional, Dict, Any
import logging

from backend.cache.redis_client import get_redis_client, RedisKeyManager
from backend.config import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器"""
    
    def __init__(self):
        self.redis = get_redis_client()
        self.key_manager = RedisKeyManager()
        self.default_ttl = settings.CACHE_TTL_SECONDS
    
    async def cache_recommendations(
        self, 
        user_id: int, 
        recommendations: List[int],
        ttl: Optional[int] = None
    ) -> None:
        """
        缓存推荐结果
        
        Args:
            user_id: 用户ID
            recommendations: 推荐游戏ID列表
            ttl: 过期时间（秒）
        """
        key = self.key_manager.recommendation_cache_key(user_id)
        
        # 序列化推荐结果
        recommendations_json = json.dumps(recommendations)
        
        # 设置缓存
        ttl = ttl or self.default_ttl
        await self.redis.setex(key, ttl, recommendations_json)
        
        logger.debug(f"Cached recommendations for user {user_id}, TTL: {ttl}s")
    
    async def get_cached_recommendations(self, user_id: int) -> Optional[List[int]]:
        """
        获取缓存的推荐结果
        
        Args:
            user_id: 用户ID
            
        Returns:
            推荐游戏ID列表或None
        """
        key = self.key_manager.recommendation_cache_key(user_id)
        
        recommendations_json = await self.redis.get(key)
        if not recommendations_json:
            return None
        
        try:
            recommendations = json.loads(recommendations_json)
            logger.debug(f"Cache hit for user {user_id} recommendations")
            return recommendations
        except Exception as e:
            logger.error(f"Failed to deserialize cached recommendations for user {user_id}: {e}")
            return None
    
    async def invalidate_user_cache(self, user_id: int) -> None:
        """
        清除用户相关缓存
        
        Args:
            user_id: 用户ID
        """
        keys_to_delete = [
            self.key_manager.recommendation_cache_key(user_id),
            self.key_manager.user_profile_key(user_id),
        ]
        
        # 批量删除
        if keys_to_delete:
            await self.redis.delete(*keys_to_delete)
            logger.info(f"Invalidated cache for user {user_id}")
    
    async def cache_user_profile(
        self, 
        user_id: int, 
        profile_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> None:
        """
        缓存用户资料
        
        Args:
            user_id: 用户ID
            profile_data: 用户资料数据
            ttl: 过期时间（秒）
        """
        key = self.key_manager.user_profile_key(user_id)
        
        # 序列化用户资料
        profile_json = json.dumps(profile_data, ensure_ascii=False)
        
        # 设置缓存
        ttl = ttl or self.default_ttl
        await self.redis.setex(key, ttl, profile_json)
        
        logger.debug(f"Cached profile for user {user_id}")
    
    async def get_cached_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        获取缓存的用户资料
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户资料数据或None
        """
        key = self.key_manager.user_profile_key(user_id)
        
        profile_json = await self.redis.get(key)
        if not profile_json:
            return None
        
        try:
            return json.loads(profile_json)
        except Exception as e:
            logger.error(f"Failed to deserialize cached profile for user {user_id}: {e}")
            return None
    
    async def set_cache(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> None:
        """
        通用缓存设置
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
        """
        # 序列化值
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, ensure_ascii=False)
        else:
            value_str = str(value)
        
        # 设置缓存
        if ttl:
            await self.redis.setex(key, ttl, value_str)
        else:
            await self.redis.set(key, value_str)
    
    async def get_cache(self, key: str) -> Optional[str]:
        """
        通用缓存获取
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值或None
        """
        return await self.redis.get(key)
    
    async def delete_cache(self, *keys: str) -> int:
        """
        删除缓存
        
        Args:
            keys: 要删除的键
            
        Returns:
            删除的键数量
        """
        if keys:
            return await self.redis.delete(*keys)
        return 0
    
    async def exists(self, key: str) -> bool:
        """
        检查键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在
        """
        return bool(await self.redis.exists(key))
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            缓存统计数据
        """
        info = await self.redis.info()
        
        return {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory": info.get("used_memory", 0),
            "used_memory_human": info.get("used_memory_human", "0B"),
            "keyspace_hits": info.get("keyspace_hits", 0),
            "keyspace_misses": info.get("keyspace_misses", 0),
            "total_commands_processed": info.get("total_commands_processed", 0),
        }
    
    async def clear_all_cache(self) -> None:
        """
        清除所有缓存（危险操作，仅用于测试）
        """
        await self.redis.flushdb()
        logger.warning("All cache cleared!")


# 全局缓存管理器实例（懒加载）
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """
    获取缓存管理器实例（懒加载）
    
    Returns:
        CacheManager实例
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager


# 为了向后兼容，创建一个属性访问器
# 注意：这会在第一次访问时初始化，确保 Redis 已经初始化
class _CacheManagerProxy:
    """缓存管理器代理，实现懒加载"""
    def __getattr__(self, name):
        return getattr(get_cache_manager(), name)


cache_manager = _CacheManagerProxy()
