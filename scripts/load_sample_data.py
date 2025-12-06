"""
加载示例数据脚本
"""

import asyncio
import sys
import random
import time
import logging
from typing import List, Dict
from pathlib import Path
import numpy as np

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database.connection import init_db, get_db_session
from backend.database.crud.user_crud import create_user, create_user_interaction
from backend.cache.redis_client import init_redis
from backend.cache.feature_store import FeatureStore
from backend.auth.password_utils import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_sample_users(db_session, num_users: int = 100) -> List[int]:
    """创建示例用户"""
    logger.info(f"Creating {num_users} sample users...")
    
    user_ids = []
    
    for i in range(num_users):
        try:
            user = await create_user(
                db=db_session,
                username=f"user_{i+1:04d}",
                email=f"user{i+1:04d}@example.com",
                password_hash=hash_password("password123")
            )
            user_ids.append(user.user_id)
            
            if (i + 1) % 20 == 0:
                logger.info(f"Created {i + 1} users...")
                
        except Exception as e:
            logger.error(f"Failed to create user {i+1}: {e}")
    
    logger.info(f"Successfully created {len(user_ids)} users")
    return user_ids


async def create_sample_interactions(db_session, user_ids: List[int], num_games: int = 1000):
    """创建示例交互数据"""
    logger.info(f"Creating sample interactions for {len(user_ids)} users and {num_games} games...")
    
    current_time = int(time.time())
    interaction_count = 0
    
    for user_id in user_ids:
        # 每个用户随机交互5-50个游戏
        num_interactions = random.randint(5, 50)
        
        # 随机选择游戏
        interacted_games = random.sample(range(1, num_games + 1), num_interactions)
        
        for i, game_id in enumerate(interacted_games):
            try:
                # 生成随机时间戳（过去30天内）
                timestamp = current_time - random.randint(0, 30 * 24 * 3600) + i * 3600
                
                # 生成随机游玩时长
                play_hours = random.uniform(0.5, 100.0)
                
                await create_user_interaction(
                    db=db_session,
                    user_id=user_id,
                    product_id=game_id,
                    timestamp=timestamp,
                    play_hours=play_hours,
                    early_access=random.choice([True, False])
                )
                
                interaction_count += 1
                
            except Exception as e:
                logger.error(f"Failed to create interaction for user {user_id}, game {game_id}: {e}")
        
        if user_id % 10 == 0:
            logger.info(f"Created interactions for {user_id} users...")
    
    logger.info(f"Successfully created {interaction_count} interactions")


async def load_sample_embeddings(feature_store: FeatureStore, num_users: int, num_games: int):
    """加载示例嵌入向量"""
    logger.info(f"Loading sample embeddings for {num_users} users and {num_games} games...")
    
    embedding_dim = 64
    
    # 生成用户嵌入
    user_embeddings = {}
    for user_id in range(1, num_users + 1):
        # 生成随机嵌入向量
        embedding = np.random.normal(0, 0.1, embedding_dim).astype(np.float32)
        # 归一化
        embedding = embedding / np.linalg.norm(embedding)
        user_embeddings[user_id] = embedding
    
    # 生成物品嵌入
    item_embeddings = {}
    for item_id in range(1, num_games + 1):
        embedding = np.random.normal(0, 0.1, embedding_dim).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        item_embeddings[item_id] = embedding
    
    # 缓存嵌入向量
    await feature_store.cache_embeddings(
        model_name="lightgcn",
        user_embeddings=user_embeddings,
        item_embeddings=item_embeddings
    )
    
    logger.info("Sample embeddings loaded successfully")


async def load_sample_popular_games(feature_store: FeatureStore, num_games: int):
    """加载示例热门游戏数据"""
    logger.info("Loading sample popular games...")
    
    # 生成热门游戏列表（基于随机分数）
    popular_games = []
    for game_id in range(1, num_games + 1):
        # 使用幂律分布生成分数，使得少数游戏非常热门
        score = random.paretovariate(1.5) * 1000
        popular_games.append((game_id, score))
    
    # 按分数排序
    popular_games.sort(key=lambda x: x[1], reverse=True)
    
    # 只保留前500个
    popular_games = popular_games[:500]
    
    await feature_store.update_popular_games(popular_games)
    
    logger.info(f"Loaded {len(popular_games)} popular games")


async def load_sample_game_metadata(feature_store: FeatureStore, num_games: int):
    """加载示例游戏元数据"""
    logger.info(f"Loading sample game metadata for {num_games} games...")
    
    genres = ["Action", "Adventure", "RPG", "Strategy", "Simulation", "Sports", "Racing", "Puzzle"]
    developers = ["Studio A", "Studio B", "Studio C", "Indie Dev", "Big Corp", "Creative Team"]
    
    for game_id in range(1, min(num_games + 1, 100)):  # 只为前100个游戏加载元数据
        metadata = {
            "title": f"Awesome Game {game_id}",
            "app_name": f"awesome_game_{game_id}",
            "genres": random.sample(genres, random.randint(1, 3)),
            "tags": ["Singleplayer", "Multiplayer", "Story Rich"],
            "developer": random.choice(developers),
            "publisher": random.choice(developers),
            "metascore": random.randint(60, 95),
            "sentiment": random.choice(["Very Positive", "Positive", "Mixed", "Negative"]),
            "release_date": f"202{random.randint(0, 3)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
            "price": round(random.uniform(9.99, 59.99), 2)
        }
        
        await feature_store.cache_game_metadata(game_id, metadata)
    
    logger.info("Sample game metadata loaded")


async def build_sample_genre_index(feature_store: FeatureStore):
    """构建示例类型索引"""
    logger.info("Building sample genre index...")
    
    genres = ["Action", "Adventure", "RPG", "Strategy", "Simulation", "Sports", "Racing", "Puzzle"]
    
    genre_games = {}
    for genre in genres:
        # 每个类型随机分配一些游戏
        game_count = random.randint(50, 200)
        games = random.sample(range(1, 1001), game_count)
        genre_games[genre] = games
    
    await feature_store.build_genre_index(genre_games)
    
    logger.info("Genre index built successfully")


async def main():
    """主函数"""
    try:
        # 初始化数据库和Redis
        await init_db()
        await init_redis()
        
        # 创建FeatureStore实例
        feature_store = FeatureStore()
        
        # 获取数据库会话
        async with get_db_session() as db:
            # 1. 创建示例用户
            user_ids = await create_sample_users(db, num_users=50)
            
            # 2. 创建示例交互数据
            await create_sample_interactions(db, user_ids, num_games=500)
        
        # 3. 加载示例嵌入向量
        await load_sample_embeddings(feature_store, num_users=50, num_games=500)
        
        # 4. 加载热门游戏数据
        await load_sample_popular_games(feature_store, num_games=500)
        
        # 5. 加载游戏元数据
        await load_sample_game_metadata(feature_store, num_games=500)
        
        # 6. 构建类型索引
        await build_sample_genre_index(feature_store)
        
        logger.info("Sample data loading completed successfully!")
        
    except Exception as e:
        logger.error(f"Sample data loading failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
