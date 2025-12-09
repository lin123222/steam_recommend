"""
基于嵌入的召回（使用 FAISS 优化）

支持动态用户向量融合：当用户交互次数达到阈值后，
将用户交互过的游戏向量与原始用户向量进行加权融合，
实现推荐结果的实时动态调整。
"""

import time
import numpy as np
from typing import List, Tuple, Optional, Dict
from backend.recall.base_recall import BaseRecall
from backend.cache.feature_store import FeatureStore
from backend.cache.faiss_index import get_faiss_index_manager
from backend.config import settings


class EmbeddingRecall(BaseRecall):
    """基于嵌入的召回器（使用 FAISS 进行高效向量搜索，支持动态向量融合）"""
    
    def __init__(self, model_name: str = "lightgcn", use_faiss: bool = True, index_type: str = "IVF"):
        """
        初始化嵌入召回器
        
        Args:
            model_name: 模型名称
            use_faiss: 是否使用 FAISS（默认 True）
            index_type: FAISS 索引类型 (IVF, HNSW, Flat)
        """
        super().__init__(f"embedding_{model_name}")
        self.model_name = model_name
        self.use_faiss = use_faiss
        self.feature_store = FeatureStore()
        
        # 初始化 FAISS 索引管理器
        if self.use_faiss:
            self.faiss_manager = get_faiss_index_manager(model_name, index_type)
            self._index_initialized = False
        else:
            self.faiss_manager = None
            self._index_initialized = True  # 不使用 FAISS 时不需要初始化
    
    async def _ensure_index_initialized(self) -> bool:
        """确保 FAISS 索引已初始化"""
        if not self.use_faiss or self._index_initialized:
            return True
        
        try:
            # 尝试构建索引
            success = await self.faiss_manager.build_index(force_rebuild=False)
            if success:
                self._index_initialized = True
                self.logger.info(
                    f"FAISS index initialized: {self.faiss_manager.get_index_size()} vectors"
                )
            return success
        except Exception as e:
            self.logger.error(f"Failed to initialize FAISS index: {e}")
            # 如果 FAISS 初始化失败，回退到原始方法
            self.use_faiss = False
            return False
    
    async def recall(
        self, 
        user_id: int, 
        top_k: int = 500,
        exclude_played: bool = True,
        use_dynamic_fusion: bool = True,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        基于用户嵌入的召回（支持动态向量融合）
        
        当 use_dynamic_fusion=True 且用户交互次数 >= 阈值时，
        会使用动态融合后的用户向量进行召回，实现实时推荐调整。
        
        Args:
            user_id: 用户ID
            top_k: 召回数量
            exclude_played: 是否排除已玩游戏
            use_dynamic_fusion: 是否启用动态向量融合
            **kwargs: 其他参数
            
        Returns:
            List[(product_id, score)]: 候选集
        """
        start_time = time.time()
        used_dynamic = False
        
        try:
            # 获取用户嵌入（根据配置决定是否使用动态融合）
            if use_dynamic_fusion and settings.DYNAMIC_FUSION_ENABLED:
                user_embedding = await self.feature_store.get_dynamic_user_embedding(
                    user_id,
                    self.model_name,
                    min_interactions=settings.DYNAMIC_FUSION_MIN_INTERACTIONS,
                    fusion_weight=settings.DYNAMIC_FUSION_WEIGHT,
                    max_sequence_len=settings.DYNAMIC_FUSION_MAX_SEQUENCE,
                    use_time_decay=settings.DYNAMIC_FUSION_TIME_DECAY
                )
                # 检查是否实际使用了动态融合
                user_sequence = await self.feature_store.get_user_sequence(user_id, 1)
                used_dynamic = len(user_sequence) >= settings.DYNAMIC_FUSION_MIN_INTERACTIONS
            else:
                user_embedding = await self.feature_store.get_user_embedding(
                    user_id, self.model_name
                )
            
            if user_embedding is None:
                self.logger.warning(f"No embedding found for user {user_id}")
                return []
            
            # 使用 FAISS 进行搜索
            if self.use_faiss:
                # 确保索引已初始化
                if not await self._ensure_index_initialized():
                    # 如果初始化失败，回退到原始方法
                    return await self._recall_legacy(user_id, top_k, exclude_played, **kwargs)
                
                # 获取用户已玩游戏（用于排除）
                exclude_ids = None
                if exclude_played:
                    exclude_ids = await self.feature_store.get_user_sequence(user_id)
                
                # 使用 FAISS 搜索
                candidates = self.faiss_manager.search(
                    user_embedding,
                    top_k=top_k,
                    exclude_ids=exclude_ids
                )
                
            else:
                # 使用原始方法（回退方案）
                candidates = await self._recall_legacy(user_id, top_k, exclude_played, **kwargs)
            
            # 记录统计信息
            elapsed_time = time.time() - start_time
            fusion_info = " (dynamic fusion)" if used_dynamic else ""
            self.logger.info(
                f"Recall completed for user {user_id}{fusion_info}: "
                f"{len(candidates)} candidates in {elapsed_time:.3f}s"
            )
            
            return candidates
            
        except Exception as e:
            self.logger.error(f"Embedding recall failed for user {user_id}: {e}", exc_info=True)
            # 如果 FAISS 搜索失败，尝试回退到原始方法
            if self.use_faiss:
                self.logger.warning("Falling back to legacy recall method")
                return await self._recall_legacy(user_id, top_k, exclude_played, **kwargs)
            return []
    
    async def _recall_legacy(
        self,
        user_id: int,
        top_k: int,
        exclude_played: bool = True,
        **kwargs
    ) -> List[Tuple[int, float]]:
        """
        原始召回方法（不使用 FAISS，作为回退方案）
        
        Args:
            user_id: 用户ID
            top_k: 召回数量
            exclude_played: 是否排除已玩游戏
            
        Returns:
            候选集
        """
        try:
            # 获取用户嵌入
            user_embedding = await self.feature_store.get_user_embedding(
                user_id, self.model_name
            )
            
            if user_embedding is None:
                return []
            
            # 获取候选物品（这里简化处理，实际应该有更智能的候选集生成）
            candidate_items = await self._get_candidate_items(user_id, top_k * 2)
            
            if not candidate_items:
                return []
            
            # 获取候选物品的嵌入
            item_embeddings = await self.feature_store.get_batch_item_embeddings(
                candidate_items, self.model_name
            )
            
            if not item_embeddings:
                return []
            
            # 排除已玩游戏
            if exclude_played:
                played_games = set(await self.feature_store.get_user_sequence(user_id))
                item_embeddings = {
                    item_id: emb for item_id, emb in item_embeddings.items()
                    if item_id not in played_games
                }
            
            # 计算相似度分数
            candidates = []
            for item_id, item_embedding in item_embeddings.items():
                # 计算余弦相似度
                similarity = self._cosine_similarity(user_embedding, item_embedding)
                candidates.append((item_id, float(similarity)))
            
            # 按相似度排序
            candidates.sort(key=lambda x: x[1], reverse=True)
            
            # 取前top_k个
            return candidates[:top_k]
            
        except Exception as e:
            self.logger.error(f"Legacy recall failed for user {user_id}: {e}")
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
            
            # 使用 FAISS 搜索
            if self.use_faiss and await self._ensure_index_initialized():
                # 排除目标物品本身
                result = self.faiss_manager.search(
                    target_embedding,
                    top_k=top_k + 1,  # 多取一个，然后过滤掉自己
                    exclude_ids=[item_id]
                )
                # 确保不超过 top_k
                result = result[:top_k]
            else:
                # 使用原始方法
                candidate_items = await self._get_candidate_items(0, top_k * 2)
                candidate_items = [cid for cid in candidate_items if cid != item_id]
                
                item_embeddings = await self.feature_store.get_batch_item_embeddings(
                    candidate_items, self.model_name
                )
                
                similarities = []
                for candidate_id, candidate_embedding in item_embeddings.items():
                    similarity = self._cosine_similarity(target_embedding, candidate_embedding)
                    similarities.append((candidate_id, float(similarity)))
                
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
