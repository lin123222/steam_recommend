"""
召回基类
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class BaseRecall(ABC):
    """召回基类"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    async def recall(
        self, 
        user_id: int, 
        top_k: int = 500,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        召回候选集
        
        Args:
            user_id: 用户ID
            top_k: 召回数量
            **kwargs: 其他参数
            
        Returns:
            List[(product_id, score)]: 候选集
        """
        pass
    
    async def batch_recall(
        self,
        user_ids: List[int],
        top_k: int = 500,
        **kwargs
    ) -> List[List[Tuple[int, float]]]:
        """
        批量召回
        
        Args:
            user_ids: 用户ID列表
            top_k: 召回数量
            **kwargs: 其他参数
            
        Returns:
            每个用户的候选集列表
        """
        results = []
        for user_id in user_ids:
            try:
                candidates = await self.recall(user_id, top_k, **kwargs)
                results.append(candidates)
            except Exception as e:
                self.logger.error(f"Failed to recall for user {user_id}: {e}")
                results.append([])
        
        return results
    
    def get_name(self) -> str:
        """获取召回器名称"""
        return self.name
    
    def log_recall_stats(
        self, 
        user_id: int, 
        candidates_count: int, 
        elapsed_time: float
    ) -> None:
        """
        记录召回统计信息
        
        Args:
            user_id: 用户ID
            candidates_count: 候选数量
            elapsed_time: 耗时（秒）
        """
        self.logger.info(
            f"Recall completed for user {user_id}: "
            f"{candidates_count} candidates in {elapsed_time:.3f}s"
        )
