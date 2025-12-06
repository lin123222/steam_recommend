"""
排序策略管理器
"""

import time
from typing import List, Tuple, Optional, Dict, Any
import logging

from backend.ranking.base_ranker import BaseRanker
from backend.ranking.rule_ranker import RuleBasedRanker
from backend.ranking.business_filter import BusinessFilter
from backend.ranking.diversity_controller import DiversityController

logger = logging.getLogger(__name__)


class RankingStrategy:
    """排序策略管理器"""
    
    def __init__(self):
        # 初始化各个组件
        self.rule_ranker = RuleBasedRanker()
        self.business_filter = BusinessFilter()
        self.diversity_controller = DiversityController()
        
        self.logger = logging.getLogger(__name__)
    
    async def rank_and_filter(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        strategy: str = "default",
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        完整的排序和过滤流程
        
        Args:
            candidates: 召回的候选集
            user_id: 用户ID
            strategy: 排序策略 (default, diversity_focused, quality_focused)
            **kwargs: 其他参数
            
        Returns:
            排序和过滤后的候选集
        """
        start_time = time.time()
        
        try:
            if not candidates:
                return candidates
            
            self.logger.info(
                f"Starting ranking and filtering for user {user_id}: "
                f"{len(candidates)} candidates, strategy={strategy}"
            )
            
            # 1. 排序阶段
            ranking_start = time.time()
            ranked_candidates = await self._apply_ranking(
                candidates, user_id, strategy, **kwargs
            )
            ranking_time = (time.time() - ranking_start) * 1000
            
            # 2. 业务过滤阶段
            filter_start = time.time()
            filtered_candidates = await self.business_filter.filter(
                ranked_candidates, user_id, **kwargs
            )
            filter_time = (time.time() - filter_start) * 1000
            
            # 3. 多样性控制阶段
            diversity_start = time.time()
            final_candidates = await self._apply_diversity_control(
                filtered_candidates, user_id, strategy, **kwargs
            )
            diversity_time = (time.time() - diversity_start) * 1000
            
            total_time = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"Ranking and filtering completed for user {user_id}: "
                f"{len(candidates)} -> {len(final_candidates)} candidates, "
                f"ranking: {ranking_time:.2f}ms, "
                f"filter: {filter_time:.2f}ms, "
                f"diversity: {diversity_time:.2f}ms, "
                f"total: {total_time:.2f}ms"
            )
            
            return final_candidates
            
        except Exception as e:
            self.logger.error(f"Ranking and filtering failed for user {user_id}: {e}")
            return candidates  # 返回原始候选集
    
    async def _apply_ranking(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        strategy: str,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        应用排序策略
        
        Args:
            candidates: 候选集
            user_id: 用户ID
            strategy: 排序策略
            **kwargs: 其他参数
            
        Returns:
            排序后的候选集
        """
        if strategy == "quality_focused":
            # 质量优先：增加评分权重
            self.rule_ranker.update_weights({
                "recall_score": 0.3,
                "genre_match": 0.2,
                "rating_boost": 0.5,
            })
        elif strategy == "diversity_focused":
            # 多样性优先：平衡各个因子
            self.rule_ranker.update_weights({
                "recall_score": 0.4,
                "genre_match": 0.3,
                "rating_boost": 0.3,
            })
        else:
            # 默认策略
            self.rule_ranker.update_weights({
                "recall_score": 0.5,
                "genre_match": 0.3,
                "rating_boost": 0.2,
            })
        
        # 应用规则排序
        return await self.rule_ranker.rank(candidates, user_id, **kwargs)
    
    async def _apply_diversity_control(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        strategy: str,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        应用多样性控制
        
        Args:
            candidates: 候选集
            user_id: 用户ID
            strategy: 排序策略
            **kwargs: 其他参数
            
        Returns:
            应用多样性控制后的候选集
        """
        # 根据策略调整多样性强度
        if strategy == "diversity_focused":
            diversity_strength = 0.8  # 高多样性
        elif strategy == "quality_focused":
            diversity_strength = 0.2  # 低多样性，更注重质量
        else:
            diversity_strength = 0.5  # 默认多样性
        
        # 从kwargs中获取用户指定的多样性强度
        diversity_strength = kwargs.get("diversity_strength", diversity_strength)
        
        return await self.diversity_controller.apply_diversity_control(
            candidates, user_id, diversity_strength
        )
    
    async def rank_only(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        ranker_type: str = "rule_based",
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        仅排序，不应用过滤
        
        Args:
            candidates: 候选集
            user_id: 用户ID
            ranker_type: 排序器类型
            **kwargs: 其他参数
            
        Returns:
            排序后的候选集
        """
        if ranker_type == "rule_based":
            return await self.rule_ranker.rank(candidates, user_id, **kwargs)
        else:
            self.logger.warning(f"Unknown ranker type: {ranker_type}, using rule_based")
            return await self.rule_ranker.rank(candidates, user_id, **kwargs)
    
    async def filter_only(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        仅过滤，不排序
        
        Args:
            candidates: 候选集
            user_id: 用户ID
            **kwargs: 其他参数
            
        Returns:
            过滤后的候选集
        """
        return await self.business_filter.filter(candidates, user_id, **kwargs)
    
    def update_ranking_config(
        self,
        ranking_weights: Dict[str, float] = None,
        filter_rules: Dict[str, Any] = None,
        diversity_params: Dict[str, Any] = None
    ) -> None:
        """
        更新排序配置
        
        Args:
            ranking_weights: 排序权重配置
            filter_rules: 过滤规则配置
            diversity_params: 多样性参数配置
        """
        if ranking_weights:
            self.rule_ranker.update_weights(ranking_weights)
            self.logger.info(f"Updated ranking weights: {ranking_weights}")
        
        if filter_rules:
            self.business_filter.update_filter_rules(**filter_rules)
            self.logger.info(f"Updated filter rules: {filter_rules}")
        
        if diversity_params:
            self.diversity_controller.update_diversity_parameters(**diversity_params)
            self.logger.info(f"Updated diversity parameters: {diversity_params}")
    
    def get_ranking_config(self) -> Dict[str, Any]:
        """
        获取当前排序配置
        
        Returns:
            排序配置字典
        """
        return {
            "ranking_weights": self.rule_ranker.weights,
            "filter_rules": {
                "max_same_developer": self.business_filter.max_same_developer,
                "max_same_genre": self.business_filter.max_same_genre,
            },
            "diversity_params": {
                "genre_diversity_weight": self.diversity_controller.genre_diversity_weight,
                "developer_diversity_weight": self.diversity_controller.developer_diversity_weight,
                "price_diversity_weight": self.diversity_controller.price_diversity_weight,
                "temporal_diversity_weight": self.diversity_controller.temporal_diversity_weight,
                "diversity_window": self.diversity_controller.diversity_window,
            }
        }
