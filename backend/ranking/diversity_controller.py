"""
多样性控制器
"""

import json
from typing import List, Tuple, Dict, Any, Set
from collections import defaultdict
import random
import logging

from backend.cache.feature_store import FeatureStore

logger = logging.getLogger(__name__)


class DiversityController:
    """多样性控制器"""
    
    def __init__(self):
        self.feature_store = FeatureStore()
        self.logger = logging.getLogger(__name__)
        
        # 多样性控制参数
        self.genre_diversity_weight = 0.3      # 类型多样性权重
        self.developer_diversity_weight = 0.2   # 开发商多样性权重
        self.price_diversity_weight = 0.1       # 价格多样性权重
        self.temporal_diversity_weight = 0.2    # 时间多样性权重
        
        # 多样性窗口大小
        self.diversity_window = 5  # 在前N个推荐中控制多样性
    
    async def apply_diversity_control(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        diversity_strength: float = 0.5
    ) -> List[Tuple[int, float]]:
        """
        应用多样性控制
        
        Args:
            candidates: 排序后的候选集
            user_id: 用户ID
            diversity_strength: 多样性强度 (0-1)
            
        Returns:
            应用多样性控制后的候选集
        """
        try:
            if not candidates or len(candidates) <= self.diversity_window:
                return candidates
            
            # 获取游戏元数据
            candidates_with_metadata = await self._enrich_with_metadata(candidates)
            
            # 应用多样性重排序
            diversified = await self._diversify_recommendations(
                candidates_with_metadata, diversity_strength
            )
            
            # 返回不带元数据的结果
            result = [(item_id, score) for item_id, score, _ in diversified]
            
            self.logger.info(
                f"Applied diversity control for user {user_id}: "
                f"strength={diversity_strength}"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Diversity control failed for user {user_id}: {e}")
            return candidates
    
    async def _enrich_with_metadata(
        self, 
        candidates: List[Tuple[int, float]]
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        为候选集添加元数据
        
        Args:
            candidates: 候选集
            
        Returns:
            带元数据的候选集
        """
        enriched = []
        
        for item_id, score in candidates:
            metadata = await self.feature_store.get_game_metadata(item_id)
            if not metadata:
                metadata = {}
            enriched.append((item_id, score, metadata))
        
        return enriched
    
    async def _diversify_recommendations(
        self, 
        candidates: List[Tuple[int, float, Dict[str, Any]]], 
        diversity_strength: float
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        多样性重排序
        
        Args:
            candidates: 带元数据的候选集
            diversity_strength: 多样性强度
            
        Returns:
            多样性重排序后的候选集
        """
        if len(candidates) <= 1:
            return candidates
        
        # 分离高质量候选（前diversity_window个）和其余候选
        high_quality = candidates[:self.diversity_window]
        remaining = candidates[self.diversity_window:]
        
        # 对高质量候选进行多样性重排序
        diversified_high_quality = self._rerank_for_diversity(
            high_quality, diversity_strength
        )
        
        # 合并结果
        return diversified_high_quality + remaining
    
    def _rerank_for_diversity(
        self, 
        candidates: List[Tuple[int, float, Dict[str, Any]]], 
        diversity_strength: float
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        为多样性重新排序
        
        使用贪心算法选择多样性最高的候选
        """
        if len(candidates) <= 1:
            return candidates
        
        selected = []
        remaining = candidates.copy()
        
        # 选择第一个（分数最高的）
        selected.append(remaining.pop(0))
        
        # 贪心选择剩余候选
        while remaining and len(selected) < len(candidates):
            best_candidate = None
            best_score = -1
            best_index = -1
            
            for i, candidate in enumerate(remaining):
                # 计算多样性分数
                diversity_score = self._calculate_diversity_score(
                    candidate, selected
                )
                
                # 结合原始分数和多样性分数
                combined_score = (
                    (1 - diversity_strength) * candidate[1] +  # 原始分数
                    diversity_strength * diversity_score        # 多样性分数
                )
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_candidate = candidate
                    best_index = i
            
            if best_candidate:
                selected.append(remaining.pop(best_index))
            else:
                break
        
        return selected
    
    def _calculate_diversity_score(
        self, 
        candidate: Tuple[int, float, Dict[str, Any]], 
        selected: List[Tuple[int, float, Dict[str, Any]]]
    ) -> float:
        """
        计算候选与已选择项目的多样性分数
        
        Args:
            candidate: 候选项目
            selected: 已选择的项目列表
            
        Returns:
            多样性分数 (0-1，越高越多样)
        """
        if not selected:
            return 1.0
        
        item_id, score, metadata = candidate
        
        # 计算各维度的多样性
        genre_diversity = self._calculate_genre_diversity(metadata, selected)
        developer_diversity = self._calculate_developer_diversity(metadata, selected)
        price_diversity = self._calculate_price_diversity(metadata, selected)
        temporal_diversity = self._calculate_temporal_diversity(metadata, selected)
        
        # 加权平均
        total_diversity = (
            genre_diversity * self.genre_diversity_weight +
            developer_diversity * self.developer_diversity_weight +
            price_diversity * self.price_diversity_weight +
            temporal_diversity * self.temporal_diversity_weight
        )
        
        # 归一化
        total_weight = (
            self.genre_diversity_weight +
            self.developer_diversity_weight +
            self.price_diversity_weight +
            self.temporal_diversity_weight
        )
        
        return total_diversity / total_weight if total_weight > 0 else 0.0
    
    def _calculate_genre_diversity(
        self, 
        metadata: Dict[str, Any], 
        selected: List[Tuple[int, float, Dict[str, Any]]]
    ) -> float:
        """计算类型多样性"""
        try:
            candidate_genres = set(self._parse_genres(metadata.get("genres", [])))
            
            if not candidate_genres:
                return 0.5  # 中性分数
            
            # 计算与已选择项目的类型重叠度
            total_overlap = 0
            for _, _, selected_metadata in selected:
                selected_genres = set(self._parse_genres(selected_metadata.get("genres", [])))
                if selected_genres:
                    overlap = len(candidate_genres & selected_genres) / len(candidate_genres | selected_genres)
                    total_overlap += overlap
            
            # 平均重叠度越低，多样性越高
            avg_overlap = total_overlap / len(selected) if selected else 0
            return 1.0 - avg_overlap
            
        except Exception as e:
            self.logger.error(f"Failed to calculate genre diversity: {e}")
            return 0.5
    
    def _calculate_developer_diversity(
        self, 
        metadata: Dict[str, Any], 
        selected: List[Tuple[int, float, Dict[str, Any]]]
    ) -> float:
        """计算开发商多样性"""
        try:
            candidate_developer = metadata.get("developer", "").lower()
            
            if not candidate_developer:
                return 0.5
            
            # 检查是否与已选择项目有相同开发商
            for _, _, selected_metadata in selected:
                selected_developer = selected_metadata.get("developer", "").lower()
                if candidate_developer == selected_developer:
                    return 0.0  # 相同开发商，多样性为0
            
            return 1.0  # 不同开发商，多样性为1
            
        except Exception as e:
            self.logger.error(f"Failed to calculate developer diversity: {e}")
            return 0.5
    
    def _calculate_price_diversity(
        self, 
        metadata: Dict[str, Any], 
        selected: List[Tuple[int, float, Dict[str, Any]]]
    ) -> float:
        """计算价格多样性"""
        try:
            candidate_price = metadata.get("price")
            
            if candidate_price is None:
                return 0.5
            
            # 定义价格区间
            def get_price_tier(price):
                if price == 0:
                    return "free"
                elif price < 20:
                    return "budget"
                elif price < 40:
                    return "mid"
                else:
                    return "premium"
            
            candidate_tier = get_price_tier(candidate_price)
            
            # 检查是否与已选择项目有相同价格区间
            for _, _, selected_metadata in selected:
                selected_price = selected_metadata.get("price")
                if selected_price is not None:
                    selected_tier = get_price_tier(selected_price)
                    if candidate_tier == selected_tier:
                        return 0.3  # 相同价格区间，较低多样性
            
            return 1.0  # 不同价格区间，高多样性
            
        except Exception as e:
            self.logger.error(f"Failed to calculate price diversity: {e}")
            return 0.5
    
    def _calculate_temporal_diversity(
        self, 
        metadata: Dict[str, Any], 
        selected: List[Tuple[int, float, Dict[str, Any]]]
    ) -> float:
        """计算时间多样性（发布时间）"""
        try:
            candidate_date = metadata.get("release_date")
            
            if not candidate_date:
                return 0.5
            
            try:
                candidate_year = int(candidate_date.split("-")[0])
            except (ValueError, IndexError):
                return 0.5
            
            # 定义年代区间
            def get_era(year):
                if year >= 2020:
                    return "recent"
                elif year >= 2015:
                    return "modern"
                elif year >= 2010:
                    return "classic"
                else:
                    return "retro"
            
            candidate_era = get_era(candidate_year)
            
            # 检查是否与已选择项目有相同年代
            for _, _, selected_metadata in selected:
                selected_date = selected_metadata.get("release_date")
                if selected_date:
                    try:
                        selected_year = int(selected_date.split("-")[0])
                        selected_era = get_era(selected_year)
                        if candidate_era == selected_era:
                            return 0.4  # 相同年代，较低多样性
                    except (ValueError, IndexError):
                        continue
            
            return 1.0  # 不同年代，高多样性
            
        except Exception as e:
            self.logger.error(f"Failed to calculate temporal diversity: {e}")
            return 0.5
    
    def _parse_genres(self, genres) -> List[str]:
        """解析游戏类型"""
        if isinstance(genres, str):
            try:
                return json.loads(genres)
            except:
                return []
        elif isinstance(genres, list):
            return genres
        else:
            return []
    
    def update_diversity_parameters(
        self,
        genre_weight: float = None,
        developer_weight: float = None,
        price_weight: float = None,
        temporal_weight: float = None,
        diversity_window: int = None
    ) -> None:
        """
        更新多样性控制参数
        
        Args:
            genre_weight: 类型多样性权重
            developer_weight: 开发商多样性权重
            price_weight: 价格多样性权重
            temporal_weight: 时间多样性权重
            diversity_window: 多样性窗口大小
        """
        if genre_weight is not None:
            self.genre_diversity_weight = genre_weight
        if developer_weight is not None:
            self.developer_diversity_weight = developer_weight
        if price_weight is not None:
            self.price_diversity_weight = price_weight
        if temporal_weight is not None:
            self.temporal_diversity_weight = temporal_weight
        if diversity_window is not None:
            self.diversity_window = diversity_window
        
        self.logger.info("Updated diversity control parameters")
