"""
排序基类
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseRanker(ABC):
    """排序基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    async def rank(
        self, 
        candidates: List[Tuple[int, float]], 
        user_id: int,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        排序候选集
        
        Args:
            candidates: [(product_id, recall_score)] 召回的候选集
            user_id: 用户ID
            **kwargs: 其他参数
            
        Returns:
            List[(product_id, final_score)]: 排序后的候选集
        """
        pass
    
    async def batch_rank(
        self,
        candidates_list: List[List[Tuple[int, float]]],
        user_ids: List[int],
        **kwargs
    ) -> List[List[Tuple[int, float]]]:
        """
        批量排序
        
        Args:
            candidates_list: 每个用户的候选集列表
            user_ids: 用户ID列表
            **kwargs: 其他参数
            
        Returns:
            每个用户排序后的候选集列表
        """
        results = []
        for candidates, user_id in zip(candidates_list, user_ids):
            try:
                ranked = await self.rank(candidates, user_id, **kwargs)
                results.append(ranked)
            except Exception as e:
                self.logger.error(f"Failed to rank for user {user_id}: {e}")
                results.append(candidates)  # 返回原始候选集
        
        return results
    
    def get_name(self) -> str:
        """获取排序器名称"""
        return self.name
    
    def log_ranking_stats(
        self, 
        user_id: int, 
        input_count: int,
        output_count: int,
        elapsed_time: float
    ) -> None:
        """
        记录排序统计信息
        
        Args:
            user_id: 用户ID
            input_count: 输入候选数量
            output_count: 输出候选数量
            elapsed_time: 耗时（秒）
        """
        self.logger.info(
            f"Ranking completed for user {user_id}: "
            f"{input_count} -> {output_count} candidates in {elapsed_time:.3f}s"
        )
    
    def _normalize_scores(self, candidates: List[Tuple[int, float]]) -> List[Tuple[int, float]]:
        """
        归一化分数到0-1范围
        
        Args:
            candidates: 候选集
            
        Returns:
            归一化后的候选集
        """
        if not candidates:
            return candidates
        
        scores = [score for _, score in candidates]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            # 所有分数相同，返回原始分数
            return candidates
        
        normalized = []
        for item_id, score in candidates:
            normalized_score = (score - min_score) / (max_score - min_score)
            normalized.append((item_id, normalized_score))
        
        return normalized
    
    def _calculate_diversity_penalty(
        self, 
        candidates: List[Tuple[int, float]],
        diversity_factor: float = 0.1
    ) -> List[Tuple[int, float]]:
        """
        计算多样性惩罚
        
        Args:
            candidates: 候选集
            diversity_factor: 多样性因子
            
        Returns:
            应用多样性惩罚后的候选集
        """
        # 简化实现：基于位置的多样性惩罚
        penalized = []
        
        for i, (item_id, score) in enumerate(candidates):
            # 位置越靠后，惩罚越小
            position_penalty = 1.0 - (diversity_factor * i / len(candidates))
            penalized_score = score * position_penalty
            penalized.append((item_id, penalized_score))
        
        return penalized
