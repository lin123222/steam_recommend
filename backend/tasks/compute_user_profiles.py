"""
用户画像计算脚本：基于嵌入向量批量计算所有用户的画像并存入数据库。

使用说明：
    python -m backend.tasks.compute_user_profiles

可配置项（环境变量，可选）：
    USER_EMB_PATH        默认 D:\\学科实践\\exported_with_id\\user_embeddings.npy
    ITEM_EMB_PATH        默认 D:\\学科实践\\exported_with_id\\item_embeddings.npy
    USER_MAP_PATH        默认 D:\\学科实践\\exported_with_id\\user_id_map.json
    ITEM_MAP_PATH        默认 D:\\学科实践\\exported_with_id\\item_id_map.json
    MODEL_NAME           默认 lightgcn
    BATCH_SIZE           默认 100（每批处理的用户数）
    TOP_K_GAMES          默认 50（用于分析的游戏数量）

计算内容：
    1. 用户喜好的游戏类型（favorite_genres）
    2. Gamer DNA 6维属性（策略、反应、探索、社交、收集、竞技）
    3. 玩家类型（primary_type, secondary_type）
"""

import asyncio
import json
import os
import logging
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from datetime import datetime

import numpy as np

from backend.cache.redis_client import init_redis
from backend.database.connection import init_db, get_db_session
from backend.database.models import UserProfile, GameMetadata

logger = logging.getLogger(__name__)

# 配置路径
USER_EMB_PATH = os.getenv("USER_EMB_PATH", r"D:\学科实践\exported_with_id\user_embeddings.npy")
ITEM_EMB_PATH = os.getenv("ITEM_EMB_PATH", r"D:\学科实践\exported_with_id\item_embeddings.npy")
USER_MAP_PATH = os.getenv("USER_MAP_PATH", r"D:\学科实践\exported_with_id\user_id_map.json")
ITEM_MAP_PATH = os.getenv("ITEM_MAP_PATH", r"D:\学科实践\exported_with_id\item_id_map.json")

MODEL_NAME = os.getenv("MODEL_NAME", "lightgcn")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
TOP_K_GAMES = int(os.getenv("TOP_K_GAMES", "50"))


# 游戏类型到 Gamer DNA 属性的映射权重
GENRE_TO_DNA_MAPPING = {
    # 策略属性
    "Strategy": {"策略": 1.0, "收集": 0.3},
    "Simulation": {"策略": 0.8, "收集": 0.5},
    "Puzzle": {"策略": 0.7},
    "Turn-Based": {"策略": 0.9},
    "City Builder": {"策略": 0.8, "收集": 0.4},
    "Management": {"策略": 0.7, "收集": 0.3},
    "Tower Defense": {"策略": 0.8},
    "RTS": {"策略": 0.9, "反应": 0.4},
    
    # 反应属性
    "Action": {"反应": 1.0, "竞技": 0.4},
    "Shooter": {"反应": 0.9, "竞技": 0.5},
    "FPS": {"反应": 1.0, "竞技": 0.6},
    "Fighting": {"反应": 0.9, "竞技": 0.7},
    "Platformer": {"反应": 0.7, "探索": 0.3},
    "Racing": {"反应": 0.8, "竞技": 0.5},
    "Arcade": {"反应": 0.8},
    "Beat 'em up": {"反应": 0.9},
    "Hack and Slash": {"反应": 0.9, "探索": 0.3},
    
    # 探索属性
    "Adventure": {"探索": 1.0, "收集": 0.3},
    "RPG": {"探索": 0.9, "收集": 0.5, "策略": 0.3},
    "Open World": {"探索": 1.0, "收集": 0.4},
    "Exploration": {"探索": 1.0},
    "Metroidvania": {"探索": 0.8, "反应": 0.4},
    "Survival": {"探索": 0.7, "收集": 0.5},
    "Walking Simulator": {"探索": 0.9},
    "Horror": {"探索": 0.6},
    "Mystery": {"探索": 0.7, "策略": 0.3},
    "Visual Novel": {"探索": 0.5},
    "Story Rich": {"探索": 0.7},
    
    # 社交属性
    "Multiplayer": {"社交": 1.0, "竞技": 0.4},
    "Co-op": {"社交": 0.9},
    "MMO": {"社交": 1.0, "探索": 0.5, "收集": 0.4},
    "MMORPG": {"社交": 0.9, "探索": 0.6, "收集": 0.5},
    "Party": {"社交": 0.8},
    "Local Multiplayer": {"社交": 0.7},
    "Online Co-Op": {"社交": 0.8},
    "Massively Multiplayer": {"社交": 1.0},
    
    # 收集属性
    "Casual": {"收集": 0.6},
    "Indie": {"探索": 0.4, "收集": 0.3},
    "Card Game": {"收集": 0.8, "策略": 0.5},
    "Trading Card Game": {"收集": 0.9, "策略": 0.4},
    "Roguelike": {"收集": 0.6, "探索": 0.5},
    "Roguelite": {"收集": 0.6, "探索": 0.5},
    "Crafting": {"收集": 0.8},
    "Building": {"收集": 0.7, "策略": 0.4},
    "Sandbox": {"收集": 0.6, "探索": 0.6},
    
    # 竞技属性
    "Sports": {"竞技": 1.0, "社交": 0.3},
    "Competitive": {"竞技": 1.0, "社交": 0.4},
    "eSports": {"竞技": 1.0, "社交": 0.5},
    "PvP": {"竞技": 0.9, "社交": 0.4},
    "Battle Royale": {"竞技": 0.9, "反应": 0.5},
    "MOBA": {"竞技": 0.9, "社交": 0.5, "策略": 0.4},
}

# 玩家类型定义
PLAYER_TYPES = {
    "策略": "策略家",
    "反应": "行动派", 
    "探索": "探索者",
    "社交": "社交家",
    "收集": "收藏家",
    "竞技": "竞技者"
}


class UserProfileComputer:
    """用户画像计算器"""
    
    def __init__(self):
        self.user_embeddings: Optional[np.ndarray] = None
        self.item_embeddings: Optional[np.ndarray] = None
        self.user_id_map: Dict[int, str] = {}  # index -> original_id
        self.item_id_map: Dict[int, str] = {}  # index -> original_id
        self.item_genres: Dict[int, List[str]] = {}  # product_id -> genres
        self.item_tags: Dict[int, List[str]] = {}    # product_id -> tags
        
        # 反向映射：original_id -> index
        self.user_id_to_index: Dict[int, int] = {}
        self.item_id_to_index: Dict[int, int] = {}
    
    def load_embeddings(self) -> None:
        """加载嵌入向量和ID映射"""
        logger.info("Loading embeddings and ID maps...")
        
        # 加载嵌入向量
        self.user_embeddings = np.load(USER_EMB_PATH)
        self.item_embeddings = np.load(ITEM_EMB_PATH)
        
        logger.info(f"User embeddings shape: {self.user_embeddings.shape}")
        logger.info(f"Item embeddings shape: {self.item_embeddings.shape}")
        
        # 加载ID映射
        with open(USER_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.user_id_map = {int(k): v for k, v in data.items()}
        
        with open(ITEM_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.item_id_map = {int(k): v for k, v in data.items()}
        
        # 构建反向映射
        for idx, orig_id in self.user_id_map.items():
            if orig_id != "[PAD]":
                try:
                    self.user_id_to_index[int(orig_id)] = idx
                except ValueError:
                    pass
        
        for idx, orig_id in self.item_id_map.items():
            if orig_id != "[PAD]":
                try:
                    self.item_id_to_index[int(orig_id)] = idx
                except ValueError:
                    pass
        
        logger.info(f"Loaded {len(self.user_id_to_index)} users, {len(self.item_id_to_index)} items")
    
    async def load_game_metadata(self) -> None:
        """从数据库加载游戏元数据（类型、标签）"""
        logger.info("Loading game metadata from database...")
        
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from backend.database.connection import async_session_maker
        
        if not async_session_maker:
            logger.error("Database not initialized")
            return
        
        async with async_session_maker() as db:
            stmt = select(GameMetadata)
            result = await db.execute(stmt)
            games = result.scalars().all()
            
            for game in games:
                product_id = game.product_id
                
                # 解析类型
                if game.genres:
                    self.item_genres[product_id] = [
                        g.strip() for g in game.genres.split(",") if g.strip()
                    ]
                else:
                    self.item_genres[product_id] = []
                
                # 解析标签
                if game.tags:
                    self.item_tags[product_id] = [
                        t.strip() for t in game.tags.split(",") if t.strip()
                    ]
                else:
                    self.item_tags[product_id] = []
        
        logger.info(f"Loaded metadata for {len(self.item_genres)} games")
    
    def get_user_top_games(self, user_id: int, top_k: int = 50) -> List[Tuple[int, float]]:
        """
        获取用户最偏好的游戏
        
        通过用户向量与所有游戏向量的内积计算偏好分数
        """
        if user_id not in self.user_id_to_index:
            return []
        
        user_idx = self.user_id_to_index[user_id]
        user_vec = self.user_embeddings[user_idx]
        
        # 计算与所有物品的内积
        scores = np.dot(self.item_embeddings, user_vec)
        
        # 获取 top_k 索引
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        # 转换为 (product_id, score) 列表
        results = []
        for idx in top_indices:
            if idx in self.item_id_map:
                orig_id = self.item_id_map[idx]
                if orig_id != "[PAD]":
                    try:
                        product_id = int(orig_id)
                        results.append((product_id, float(scores[idx])))
                    except ValueError:
                        pass
        
        return results

    
    def compute_user_preferences(self, user_id: int, top_k: int = 50) -> Dict:
        """
        计算用户偏好（喜爱的类型和标签）
        """
        top_games = self.get_user_top_games(user_id, top_k)
        
        if not top_games:
            return {
                "favorite_genres": [],
                "favorite_tags": [],
                "genre_scores": {},
                "tag_scores": {}
            }
        
        # 统计类型和标签分布（加权）
        genre_scores = defaultdict(float)
        tag_scores = defaultdict(float)
        
        for product_id, score in top_games:
            genres = self.item_genres.get(product_id, [])
            tags = self.item_tags.get(product_id, [])
            
            for genre in genres:
                genre_scores[genre] += score
            for tag in tags:
                tag_scores[tag] += score
        
        # 排序
        sorted_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)
        sorted_tags = sorted(tag_scores.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "favorite_genres": [g[0] for g in sorted_genres[:5]],
            "favorite_tags": [t[0] for t in sorted_tags[:10]],
            "genre_scores": dict(sorted_genres[:10]),
            "tag_scores": dict(sorted_tags[:15])
        }
    
    def compute_gamer_dna(self, user_id: int, top_k: int = 50) -> Dict:
        """
        计算用户的 Gamer DNA（6维属性）
        """
        top_games = self.get_user_top_games(user_id, top_k)
        
        if not top_games:
            return self._get_default_gamer_dna()
        
        # 计算6维属性分数
        dna_scores = {
            "策略": 0.0,
            "反应": 0.0,
            "探索": 0.0,
            "社交": 0.0,
            "收集": 0.0,
            "竞技": 0.0
        }
        
        for product_id, score in top_games:
            genres = self.item_genres.get(product_id, [])
            tags = self.item_tags.get(product_id, [])
            
            # 合并类型和标签
            all_categories = genres + tags
            
            for category in all_categories:
                if category in GENRE_TO_DNA_MAPPING:
                    mapping = GENRE_TO_DNA_MAPPING[category]
                    for attr, weight in mapping.items():
                        dna_scores[attr] += score * weight
        
        # 归一化到 0-100
        max_score = max(dna_scores.values()) if dna_scores.values() else 1
        if max_score > 0:
            for attr in dna_scores:
                dna_scores[attr] = int((dna_scores[attr] / max_score) * 100)
        
        # 确保最低值不低于20
        for attr in dna_scores:
            dna_scores[attr] = max(20, dna_scores[attr])
        
        # 构建返回数据
        stats = [
            {"name": attr, "value": score, "max": 100}
            for attr, score in dna_scores.items()
        ]
        
        # 确定主要和次要类型
        sorted_attrs = sorted(dna_scores.items(), key=lambda x: x[1], reverse=True)
        primary_type = PLAYER_TYPES.get(sorted_attrs[0][0], "探索者")
        secondary_type = PLAYER_TYPES.get(sorted_attrs[1][0], "策略家")
        
        return {
            "stats": stats,
            "primary_type": primary_type,
            "secondary_type": secondary_type,
            "raw_scores": dna_scores
        }
    
    def _get_default_gamer_dna(self) -> Dict:
        """获取默认 Gamer DNA"""
        return {
            "stats": [
                {"name": "策略", "value": 50, "max": 100},
                {"name": "反应", "value": 50, "max": 100},
                {"name": "探索", "value": 50, "max": 100},
                {"name": "社交", "value": 50, "max": 100},
                {"name": "收集", "value": 50, "max": 100},
                {"name": "竞技", "value": 50, "max": 100}
            ],
            "primary_type": "探索者",
            "secondary_type": "策略家",
            "raw_scores": {}
        }

    
    async def save_user_profile(self, user_id: int, preferences: Dict, gamer_dna: Dict) -> bool:
        """
        保存用户画像到数据库
        """
        from sqlalchemy import select, update
        from backend.database.connection import async_session_maker
        
        if not async_session_maker:
            logger.error("Database not initialized")
            return False
        
        try:
            async with async_session_maker() as db:
                # 检查是否存在
                stmt = select(UserProfile).where(UserProfile.user_id == user_id)
                result = await db.execute(stmt)
                profile = result.scalar_one_or_none()
                
                gamer_dna_stats_json = json.dumps(gamer_dna["stats"], ensure_ascii=False)
                favorite_genres_json = json.dumps(preferences["favorite_genres"], ensure_ascii=False)
                
                if profile:
                    # 更新现有记录
                    profile.gamer_dna_stats = gamer_dna_stats_json
                    profile.primary_type = gamer_dna["primary_type"]
                    profile.secondary_type = gamer_dna["secondary_type"]
                    profile.favorite_genres = favorite_genres_json
                else:
                    # 创建新记录
                    profile = UserProfile(
                        user_id=user_id,
                        member_since=datetime.now().date(),
                        gamer_dna_stats=gamer_dna_stats_json,
                        primary_type=gamer_dna["primary_type"],
                        secondary_type=gamer_dna["secondary_type"],
                        favorite_genres=favorite_genres_json
                    )
                    db.add(profile)
                
                await db.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to save profile for user {user_id}: {e}")
            return False
    
    async def compute_all_users(self, limit: Optional[int] = None) -> Dict:
        """
        批量计算所有用户的画像
        
        Args:
            limit: 限制处理的用户数量（用于测试）
        
        Returns:
            统计信息
        """
        user_ids = list(self.user_id_to_index.keys())
        
        if limit:
            user_ids = user_ids[:limit]
        
        total = len(user_ids)
        success_count = 0
        failed_count = 0
        
        logger.info(f"Starting to compute profiles for {total} users...")
        
        for i in range(0, total, BATCH_SIZE):
            batch = user_ids[i:i + BATCH_SIZE]
            batch_success = 0
            
            for user_id in batch:
                try:
                    # 计算偏好
                    preferences = self.compute_user_preferences(user_id, TOP_K_GAMES)
                    
                    # 计算 Gamer DNA
                    gamer_dna = self.compute_gamer_dna(user_id, TOP_K_GAMES)
                    
                    # 保存到数据库
                    if await self.save_user_profile(user_id, preferences, gamer_dna):
                        success_count += 1
                        batch_success += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    logger.error(f"Error computing profile for user {user_id}: {e}")
                    failed_count += 1
            
            progress = (i + len(batch)) / total * 100
            logger.info(f"Progress: {progress:.1f}% ({i + len(batch)}/{total}), batch success: {batch_success}/{len(batch)}")
        
        return {
            "total": total,
            "success": success_count,
            "failed": failed_count
        }


async def main(limit: Optional[int] = None) -> None:
    """
    主函数
    
    Args:
        limit: 限制处理的用户数量（用于测试）
    """
    logger.info("=" * 60)
    logger.info("User Profile Computation Script")
    logger.info("=" * 60)
    
    # 初始化
    await init_redis()
    await init_db()
    
    # 创建计算器
    computer = UserProfileComputer()
    
    # 加载数据
    computer.load_embeddings()
    await computer.load_game_metadata()
    
    # 计算所有用户画像
    stats = await computer.compute_all_users(limit=limit)
    
    logger.info("=" * 60)
    logger.info("Computation Complete!")
    logger.info(f"Total users: {stats['total']}")
    logger.info(f"Success: {stats['success']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info("=" * 60)


if __name__ == "__main__":
    import sys
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # 可选：从命令行参数获取限制数量
    limit = None
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
            logger.info(f"Limiting to {limit} users (test mode)")
        except ValueError:
            pass
    
    asyncio.run(main(limit=limit))
