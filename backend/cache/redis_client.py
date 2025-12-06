"""
Redis客户端管理
"""

import redis.asyncio as redis
from typing import Optional
import logging

from backend.config import get_redis_url, settings

logger = logging.getLogger(__name__)

# 全局Redis连接池
redis_pool: Optional[redis.ConnectionPool] = None
redis_client: Optional[redis.Redis] = None


async def init_redis() -> None:
    """初始化Redis连接"""
    global redis_pool, redis_client
    
    redis_url = get_redis_url()
    logger.info(f"Connecting to Redis: {redis_url}")
    
    # 创建连接池
    redis_pool = redis.ConnectionPool.from_url(
        redis_url,
        max_connections=settings.REDIS_MAX_CONNECTIONS,
        retry_on_timeout=True,
        socket_keepalive=True,
        socket_keepalive_options={},
    )
    
    # 创建Redis客户端
    redis_client = redis.Redis(
        connection_pool=redis_pool,
        decode_responses=True,  # 自动解码响应
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    
    # 测试连接
    try:
        await redis_client.ping()
        logger.info("Redis connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


async def close_redis() -> None:
    """关闭Redis连接"""
    global redis_pool, redis_client
    
    if redis_client:
        await redis_client.close()
        redis_client = None
        logger.info("Redis client closed")
    
    if redis_pool:
        await redis_pool.disconnect()
        redis_pool = None
        logger.info("Redis connection pool closed")


def get_redis_client() -> redis.Redis:
    """
    获取Redis客户端
    
    Returns:
        Redis客户端实例
        
    Raises:
        RuntimeError: Redis未初始化时抛出
    """
    if not redis_client:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    
    return redis_client


class RedisKeyManager:
    """Redis键管理器"""
    
    # 键前缀
    USER_SEQ_PREFIX = "user_seq"
    EMBEDDINGS_PREFIX = "embeddings"
    REC_CACHE_PREFIX = "rec_cache"
    POPULAR_GAMES = "popular_games"
    GENRE_INDEX_PREFIX = "genre_index"
    GAME_META_PREFIX = "game_meta"
    USER_PROFILE_PREFIX = "user_profile"
    
    @staticmethod
    def user_sequence_key(user_id: int) -> str:
        """用户序列键"""
        return f"{RedisKeyManager.USER_SEQ_PREFIX}:{user_id}"
    
    @staticmethod
    def user_embedding_key(model_name: str) -> str:
        """用户嵌入键"""
        return f"{RedisKeyManager.EMBEDDINGS_PREFIX}:{model_name}:user"
    
    @staticmethod
    def item_embedding_key(model_name: str) -> str:
        """物品嵌入键"""
        return f"{RedisKeyManager.EMBEDDINGS_PREFIX}:{model_name}:item"
    
    @staticmethod
    def recommendation_cache_key(user_id: int) -> str:
        """推荐缓存键"""
        return f"{RedisKeyManager.REC_CACHE_PREFIX}:{user_id}"
    
    @staticmethod
    def genre_index_key(genre: str) -> str:
        """类型索引键"""
        return f"{RedisKeyManager.GENRE_INDEX_PREFIX}:{genre}"
    
    @staticmethod
    def game_metadata_key(product_id: int) -> str:
        """游戏元数据键"""
        return f"{RedisKeyManager.GAME_META_PREFIX}:{product_id}"
    
    @staticmethod
    def user_profile_key(user_id: int) -> str:
        """用户资料键"""
        return f"{RedisKeyManager.USER_PROFILE_PREFIX}:{user_id}"
