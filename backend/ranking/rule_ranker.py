"""
基于规则的排序器
"""

import time
import json
from typing import List, Tuple, Dict, Any, Optional
from backend.ranking.base_ranker import BaseRanker
from backend.cache.feature_store import FeatureStore
from backend.config import settings


class RuleBasedRanker(BaseRanker):
    """基于规则的排序器"""
    
    def __init__(self):
        super().__init__("rule_based")
        self.feature_store = FeatureStore()
        
        # 排序权重配置
        self.weights = {
            "recall_score": 0.5,      # 召回分数权重
            "genre_match": 0.3,       # 类型匹配度权重
            "rating_boost": 0.2,      # 评分加权权重
        }
        
        # 时间衰减参数
        self.time_decay_factor = 0.95
        
        # 多样性控制参数
        self.diversity_penalty = 0.1
    
    async def rank(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        基于规则的排序
        
        排序公式：
        综合分数 = 召回分数 * 0.5 + 类型匹配度 * 0.3 + 评分加权 * 0.2
                 * 时间衰减因子 * 多样性惩罚因子
        """
        start_time = time.time()
        
        try:
            if not candidates:
                return candidates
            
            # 获取用户偏好信息
            user_preferences = await self._get_user_preferences(user_id)
            
            # 计算每个候选的最终分数
            scored_candidates = []
            
            for item_id, recall_score in candidates:
                # 获取游戏元数据
                game_metadata = await self.feature_store.get_game_metadata(item_id)
                
                if not game_metadata:
                    # 没有元数据，只使用召回分数
                    final_score = recall_score
                else:
                    # 计算各个分数组件
                    genre_score = await self._calculate_genre_match_score(
                        game_metadata, user_preferences
                    )
                    rating_score = self._calculate_rating_score(game_metadata)
                    
                    # 计算综合分数
                    final_score = (
                        recall_score * self.weights["recall_score"] +
                        genre_score * self.weights["genre_match"] +
                        rating_score * self.weights["rating_boost"]
                    )
                
                # 应用时间衰减
                final_score = self._apply_time_decay(final_score, game_metadata)
                
                scored_candidates.append((item_id, final_score))
            
            # 按分数排序
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # 应用多样性惩罚
            final_candidates = self._calculate_diversity_penalty(
                scored_candidates, self.diversity_penalty
            )
            
            # 重新排序
            final_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # 记录统计信息
            elapsed_time = time.time() - start_time
            self.log_ranking_stats(
                user_id, len(candidates), len(final_candidates), elapsed_time
            )
            
            return final_candidates
            
        except Exception as e:
            self.logger.error(f"Rule-based ranking failed for user {user_id}: {e}")
            return candidates  # 返回原始候选集
    
    async def _get_user_preferences(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户偏好信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户偏好字典
        """
        try:
            # 获取用户最近的游戏序列
            user_sequence = await self.feature_store.get_user_sequence(user_id, 20)
            
            if not user_sequence:
                return {"favorite_genres": [], "avg_rating": 0.0}
            
            # 统计用户偏好的游戏类型
            genre_counts = {}
            total_rating = 0.0
            rating_count = 0
            
            for game_id in user_sequence:
                metadata = await self.feature_store.get_game_metadata(game_id)
                if metadata:
                    # 统计类型偏好
                    genres = metadata.get("genres", [])
                    if isinstance(genres, str):
                        try:
                            genres = json.loads(genres)
                        except:
                            genres = []
                    
                    for genre in genres:
                        genre_counts[genre] = genre_counts.get(genre, 0) + 1
                    
                    # 统计评分偏好
                    metascore = metadata.get("metascore")
                    if metascore:
                        total_rating += metascore
                        rating_count += 1
            
            # 获取最喜欢的类型（前3个）
            favorite_genres = sorted(
                genre_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:3]
            favorite_genres = [genre for genre, _ in favorite_genres]
            
            # 计算平均评分偏好
            avg_rating = total_rating / rating_count if rating_count > 0 else 0.0
            
            return {
                "favorite_genres": favorite_genres,
                "avg_rating": avg_rating
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get user preferences for user {user_id}: {e}")
            return {"favorite_genres": [], "avg_rating": 0.0}
    
    async def _calculate_genre_match_score(
        self, 
        game_metadata: Dict[str, Any], 
        user_preferences: Dict[str, Any]
    ) -> float:
        """
        计算类型匹配度分数
        
        Args:
            game_metadata: 游戏元数据
            user_preferences: 用户偏好
            
        Returns:
            类型匹配度分数 (0-1)
        """
        try:
            game_genres = game_metadata.get("genres", [])
            if isinstance(game_genres, str):
                try:
                    game_genres = json.loads(game_genres)
                except:
                    game_genres = []
            
            favorite_genres = user_preferences.get("favorite_genres", [])
            
            if not game_genres or not favorite_genres:
                return 0.0
            
            # 计算交集比例
            genre_intersection = set(game_genres) & set(favorite_genres)
            match_score = len(genre_intersection) / len(set(game_genres) | set(favorite_genres))
            
            return min(match_score, 1.0)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate genre match score: {e}")
            return 0.0
    
    def _calculate_rating_score(self, game_metadata: Dict[str, Any]) -> float:
        """
        计算评分加权分数
        
        Args:
            game_metadata: 游戏元数据
            
        Returns:
            评分分数 (0-1)
        """
        try:
            metascore = game_metadata.get("metascore")
            if not metascore:
                return 0.5  # 默认中等分数
            
            # 将评分归一化到0-1范围（假设评分范围是0-100）
            normalized_score = min(metascore / 100.0, 1.0)
            
            return normalized_score
            
        except Exception as e:
            self.logger.error(f"Failed to calculate rating score: {e}")
            return 0.5
    
    def _apply_time_decay(
        self, 
        score: float, 
        game_metadata: Optional[Dict[str, Any]]
    ) -> float:
        """
        应用时间衰减因子
        
        Args:
            score: 原始分数
            game_metadata: 游戏元数据
            
        Returns:
            应用时间衰减后的分数
        """
        try:
            if not game_metadata:
                return score
            
            release_date = game_metadata.get("release_date")
            if not release_date:
                return score
            
            # 简化处理：根据发布年份应用衰减
            # 实际应该根据具体的时间差计算
            try:
                release_year = int(release_date.split("-")[0])
                current_year = 2023  # 可以改为动态获取当前年份
                
                year_diff = current_year - release_year
                
                # 每年衰减5%，但不低于0.7
                decay_factor = max(self.time_decay_factor ** year_diff, 0.7)
                
                return score * decay_factor
                
            except (ValueError, IndexError):
                return score
            
        except Exception as e:
            self.logger.error(f"Failed to apply time decay: {e}")
            return score
    
    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """
        更新排序权重
        
        Args:
            new_weights: 新的权重配置
        """
        self.weights.update(new_weights)
        self.logger.info(f"Updated ranking weights: {self.weights}")
    
    def update_parameters(
        self, 
        time_decay_factor: Optional[float] = None,
        diversity_penalty: Optional[float] = None
    ) -> None:
        """
        更新排序参数
        
        Args:
            time_decay_factor: 时间衰减因子
            diversity_penalty: 多样性惩罚因子
        """
        if time_decay_factor is not None:
            self.time_decay_factor = time_decay_factor
        
        if diversity_penalty is not None:
            self.diversity_penalty = diversity_penalty
        
        self.logger.info(
            f"Updated ranking parameters: "
            f"time_decay={self.time_decay_factor}, "
            f"diversity_penalty={self.diversity_penalty}"
        )
