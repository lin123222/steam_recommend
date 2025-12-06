"""
基于嵌入的召回
"""

import time
import numpy as np
from typing import List, Tuple, Optional, Dict
from backend.recall.base_recall import BaseRecall
from backend.cache.feature_store import FeatureStore


class EmbeddingRecall(BaseRecall):
    """基于嵌入的召回器"""
    
    def __init__(self, model_name: str = "lightgcn"):
        super().__init__(f"embedding_{model_name}")
        self.model_name = model_name
        self.feature_store = FeatureStore()
    
    async def recall(
        self, 
        user_id: int, 
        top_k: int = 500,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        基于用户嵌入的召回
        
        Args:
            user_id: 用户ID
            top_k: 召回数量
            **kwargs: 其他参数
            
        Returns:
            List[(product_id, score)]: 候选集
        """
        start_time = time.time()
        
        try:
            # 获取用户嵌入
            user_embedding = await self.feature_store.get_user_embedding(
                user_id, self.model_name
            )
            
            if user_embedding is None:
                self.logger.warning(f"No embedding found for user {user_id}")
                return []
            
            # 获取候选物品（这里简化处理，实际应该有更智能的候选集生成）
            candidate_items = await self._get_candidate_items(user_id, top_k * 2)
            
            if not candidate_items:
                self.logger.warning(f"No candidate items for user {user_id}")
                return []
            
            # 获取候选物品的嵌入
            item_embeddings = await self.feature_store.get_batch_item_embeddings(
                candidate_items, self.model_name
            )
            
            if not item_embeddings:
                self.logger.warning(f"No item embeddings found for candidates")
                return []
            
            # 计算相似度分数
            candidates = []
            for item_id, item_embedding in item_embeddings.items():
                # 计算余弦相似度
                similarity = self._cosine_similarity(user_embedding, item_embedding)
                candidates.append((item_id, float(similarity)))
            
            # 按相似度排序
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            # 取前top_k个
            result = candidates[:top_k]
            
            # 记录统计信息
            elapsed_time = time.time() - start_time
            self.log_recall_stats(user_id, len(result), elapsed_time)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Embedding recall failed for user {user_id}: {e}")
            return []
    
    async def _get_candidate_items(self, user_id: int, limit: int) -> List[int]:
        """
        获取候选物品集合
        
        Args:
            user_id: 用户ID
            limit: 限制数量
            
        Returns:
            候选物品ID列表
        """
        # 方法1: 从热门游戏中获取候选集
        popular_games = await self.feature_store.get_popular_games(limit=limit)
        candidate_items = [game_id for game_id, _ in popular_games]
        
        # 方法2: 可以添加基于用户历史的候选集扩展
        # user_history = await self.feature_store.get_user_sequence(user_id, 10)
        # 基于用户历史的协同过滤等...
        
        return candidate_items
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            余弦相似度
        """
        # 计算向量的模长
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        # 避免除零错误
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # 计算余弦相似度
        return np.dot(vec1, vec2) / (norm1 * norm2)
    
    async def recall_similar_items(
        self,
        item_id: int,
        top_k: int = 100
    ) -> List[Tuple[int, float]]:
        """
        召回与指定物品相似的物品
        
        Args:
            item_id: 物品ID
            top_k: 召回数量
            
        Returns:
            相似物品列表
        """
        start_time = time.time()
        
        try:
            # 获取目标物品嵌入
            target_embedding = await self.feature_store.get_item_embedding(
                item_id, self.model_name
            )
            
            if target_embedding is None:
                self.logger.warning(f"No embedding found for item {item_id}")
                return []
            
            # 获取所有候选物品
            candidate_items = await self._get_candidate_items(0, top_k * 2)  # user_id=0 for item-based
            
            # 移除目标物品本身
            candidate_items = [cid for cid in candidate_items if cid != item_id]
            
            # 获取候选物品嵌入
            item_embeddings = await self.feature_store.get_batch_item_embeddings(
                candidate_items, self.model_name
            )
            
            # 计算相似度
            similarities = []
            for candidate_id, candidate_embedding in item_embeddings.items():
                similarity = self._cosine_similarity(target_embedding, candidate_embedding)
                similarities.append((candidate_id, float(similarity)))
            
            # 排序并返回
            similarities.sort(key=lambda x: x[1], reverse=True)
            result = similarities[:top_k]
            
            elapsed_time = time.time() - start_time
            self.logger.info(
                f"Item similarity recall for item {item_id}: "
                f"{len(result)} candidates in {elapsed_time:.3f}s"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Item similarity recall failed for item {item_id}: {e}")
            return []
    
    async def recall_by_user_sequence(
        self,
        user_id: int,
        sequence_length: int = 10,
        top_k: int = 500
    ) -> List[Tuple[int, float]]:
        """
        基于用户序列的召回
        
        Args:
            user_id: 用户ID
            sequence_length: 序列长度
            top_k: 召回数量
            
        Returns:
            候选集
        """
        try:
            # 获取用户最近的交互序列
            user_sequence = await self.feature_store.get_user_sequence(
                user_id, sequence_length
            )
            
            if not user_sequence:
                self.logger.warning(f"No sequence found for user {user_id}")
                return []
            
            # 为序列中的每个物品找相似物品
            all_candidates = {}
            
            for item_id in user_sequence:
                similar_items = await self.recall_similar_items(item_id, top_k // len(user_sequence))
                
                # 累积相似度分数
                for similar_id, score in similar_items:
                    if similar_id not in user_sequence:  # 排除已交互的物品
                        if similar_id in all_candidates:
                            all_candidates[similar_id] += score
                        else:
                            all_candidates[similar_id] = score
            
            # 转换为列表并排序
            candidates = list(all_candidates.items())
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            return candidates[:top_k]
            
        except Exception as e:
            self.logger.error(f"Sequence-based recall failed for user {user_id}: {e}")
            return []
