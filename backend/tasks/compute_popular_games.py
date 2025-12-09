"""
热门游戏计算脚本：基于游戏元数据计算热门度并存入 Redis。

使用说明：
    python -m backend.tasks.compute_popular_games

计算逻辑：
    热门度分数 = metascore权重 * metascore + sentiment权重 * sentiment分数
    
    - metascore: Metacritic 评分 (0-100)
    - sentiment: Steam 用户评价情感，映射为分数

可配置项（环境变量）：
    METASCORE_WEIGHT     默认 0.6（metascore 权重）
    SENTIMENT_WEIGHT     默认 0.4（sentiment 权重）
    TOP_POPULAR_COUNT    默认 500（保留的热门游戏数量）
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Optional

from backend.cache.redis_client import init_redis
from backend.cache.feature_store import FeatureStore
from backend.database.connection import init_db, async_session_maker
from backend.database.models import GameMetadata

from sqlalchemy import select

logger = logging.getLogger(__name__)

# 配置权重
METASCORE_WEIGHT = float(__import__('os').getenv("METASCORE_WEIGHT", "0.6"))
SENTIMENT_WEIGHT = float(__import__('os').getenv("SENTIMENT_WEIGHT", "0.4"))
TOP_POPULAR_COUNT = int(__import__('os').getenv("TOP_POPULAR_COUNT", "500"))


# Steam 用户评价情感到分数的映射
SENTIMENT_SCORES = {
    # 非常正面
    "Overwhelmingly Positive": 100,
    "Very Positive": 90,
    "Positive": 80,
    "Mostly Positive": 70,
    
    # 中性
    "Mixed": 50,
    
    # 负面
    "Mostly Negative": 30,
    "Negative": 20,
    "Very Negative": 10,
    "Overwhelmingly Negative": 0,
    
    # 其他/未知
    None: 50,
    "": 50,
}


def get_sentiment_score(sentiment: Optional[str]) -> float:
    """
    将 sentiment 字符串转换为分数
    
    Args:
        sentiment: Steam 评价情感字符串
        
    Returns:
        分数 (0-100)
    """
    if not sentiment:
        return 50.0
    
    # 精确匹配
    if sentiment in SENTIMENT_SCORES:
        return float(SENTIMENT_SCORES[sentiment])
    
    # 模糊匹配（处理大小写和空格）
    sentiment_lower = sentiment.lower().strip()
    
    if "overwhelmingly positive" in sentiment_lower:
        return 100.0
    elif "very positive" in sentiment_lower:
        return 90.0
    elif "mostly positive" in sentiment_lower:
        return 70.0
    elif "positive" in sentiment_lower:
        return 80.0
    elif "overwhelmingly negative" in sentiment_lower:
        return 0.0
    elif "very negative" in sentiment_lower:
        return 10.0
    elif "mostly negative" in sentiment_lower:
        return 30.0
    elif "negative" in sentiment_lower:
        return 20.0
    elif "mixed" in sentiment_lower:
        return 50.0
    
    # 默认值
    return 50.0


def calculate_popularity_score(
    metascore: Optional[int],
    sentiment: Optional[str]
) -> float:
    """
    计算游戏的热门度分数
    
    公式: score = metascore_weight * metascore + sentiment_weight * sentiment_score
    
    Args:
        metascore: Metacritic 评分 (0-100)
        sentiment: Steam 用户评价情感
        
    Returns:
        热门度分数 (0-100)
    """
    # 获取 metascore，如果为空则使用默认值 50
    meta = float(metascore) if metascore is not None else 50.0
    
    # 确保 metascore 在 0-100 范围内
    meta = max(0.0, min(100.0, meta))
    
    # 获取 sentiment 分数
    sent_score = get_sentiment_score(sentiment)
    
    # 计算加权分数
    score = METASCORE_WEIGHT * meta + SENTIMENT_WEIGHT * sent_score
    
    return score



async def compute_popular_games() -> List[Tuple[int, float]]:
    """
    从数据库计算热门游戏列表
    
    Returns:
        热门游戏列表 [(product_id, score), ...]
    """
    logger.info("Computing popular games from database...")
    
    if not async_session_maker:
        logger.error("Database not initialized")
        return []
    
    async with async_session_maker() as db:
        # 查询所有游戏
        stmt = select(GameMetadata)
        result = await db.execute(stmt)
        games = result.scalars().all()
        
        logger.info(f"Found {len(games)} games in database")
        
        # 计算每个游戏的热门度分数
        game_scores = []
        
        for game in games:
            score = calculate_popularity_score(game.metascore, game.sentiment)
            game_scores.append((game.product_id, score))
        
        # 按分数降序排序
        game_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 只保留前 N 个
        top_games = game_scores[:TOP_POPULAR_COUNT]
        
        logger.info(f"Computed popularity scores for {len(game_scores)} games")
        logger.info(f"Top 5 games: {top_games[:5]}")
        
        return top_games


async def save_popular_games_to_redis(game_scores: List[Tuple[int, float]]) -> bool:
    """
    将热门游戏列表保存到 Redis
    
    Args:
        game_scores: 热门游戏列表 [(product_id, score), ...]
        
    Returns:
        是否成功
    """
    try:
        feature_store = FeatureStore()
        await feature_store.update_popular_games(game_scores)
        logger.info(f"Saved {len(game_scores)} popular games to Redis")
        return True
    except Exception as e:
        logger.error(f"Failed to save popular games to Redis: {e}")
        return False


async def main() -> None:
    """主函数"""
    logger.info("=" * 60)
    logger.info("Popular Games Computation Script")
    logger.info(f"Weights: metascore={METASCORE_WEIGHT}, sentiment={SENTIMENT_WEIGHT}")
    logger.info("=" * 60)
    
    # 初始化
    await init_db()
    await init_redis()
    
    # 计算热门游戏
    popular_games = await compute_popular_games()
    
    if not popular_games:
        logger.warning("No popular games computed")
        return
    
    # 保存到 Redis
    success = await save_popular_games_to_redis(popular_games)
    
    if success:
        logger.info("=" * 60)
        logger.info("Computation Complete!")
        logger.info(f"Total popular games: {len(popular_games)}")
        logger.info(f"Score range: {popular_games[-1][1]:.2f} - {popular_games[0][1]:.2f}")
        logger.info("=" * 60)
    else:
        logger.error("Failed to save popular games")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    asyncio.run(main())
