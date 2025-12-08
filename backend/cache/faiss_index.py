"""
FAISS 向量索引管理
"""

import faiss
import numpy as np
import pickle
import logging
from typing import List, Tuple, Optional, Dict
from pathlib import Path

from backend.cache.feature_store import FeatureStore
from backend.cache.redis_client import get_redis_client, RedisKeyManager
from backend.config import settings

logger = logging.getLogger(__name__)


class FaissIndexManager:
    """FAISS 索引管理器"""
    
    def __init__(self, model_name: str = "lightgcn", index_type: str = "IVF"):
        """
        初始化 FAISS 索引管理器
        
        Args:
            model_name: 模型名称
            index_type: 索引类型 (IVF, Flat, HNSW)
        """
        self.model_name = model_name
        self.index_type = index_type
        self.feature_store = FeatureStore()
        self.key_manager = RedisKeyManager()
        
        # 索引和ID映射
        self.index: Optional[faiss.Index] = None
        self.id_to_index: Dict[int, int] = {}  # item_id -> faiss_index
        self.index_to_id: Dict[int, int] = {}  # faiss_index -> item_id
        
        # 索引参数
        self.embedding_dim = settings.EMBEDDING_DIM
        self.nlist = 100  # IVF 聚类中心数
        self.nprobe = 10  # 搜索时探查的聚类数
        self.m = 32  # HNSW 参数：每个节点的连接数
        
    def _create_index(self, num_vectors: int) -> faiss.Index:
        """
        创建 FAISS 索引
        
        Args:
            num_vectors: 向量数量
            
        Returns:
            FAISS 索引对象
        """
        if self.index_type == "IVF":
            # IVF (Inverted File Index) - 适合大规模数据
            quantizer = faiss.IndexFlatIP(self.embedding_dim)  # 内积（余弦相似度需要归一化）
            nlist = min(self.nlist, num_vectors // 10)  # 确保 nlist 不超过向量数
            nlist = max(nlist, 1)  # 至少为1
            
            index = faiss.IndexIVFFlat(quantizer, self.embedding_dim, nlist)
            index.nprobe = min(self.nprobe, nlist)  # 搜索时探查的聚类数
            
            logger.info(f"Created IVF index with nlist={nlist}, nprobe={index.nprobe}")
            return index
            
        elif self.index_type == "HNSW":
            # HNSW (Hierarchical Navigable Small World) - 高质量近似搜索
            index = faiss.IndexHNSWFlat(self.embedding_dim, self.m)
            index.hnsw.efConstruction = 200  # 构建时的搜索范围
            index.hnsw.efSearch = 64  # 搜索时的搜索范围
            
            logger.info(f"Created HNSW index with m={self.m}")
            return index
            
        else:  # Flat
            # Flat - 精确搜索，适合小规模数据
            index = faiss.IndexFlatIP(self.embedding_dim)  # 内积
            logger.info("Created Flat index")
            return index
    
    async def build_index(self, force_rebuild: bool = False) -> bool:
        """
        从 Redis 构建 FAISS 索引
        
        Args:
            force_rebuild: 是否强制重建索引
            
        Returns:
            是否成功构建
        """
        try:
            redis = get_redis_client()
            key = self.key_manager.item_embedding_key(self.model_name)
            
            # 检查是否已有索引且不需要重建
            if self.index is not None and not force_rebuild:
                logger.info("Index already exists, skipping build")
                return True
            
            logger.info(f"Building FAISS index for model {self.model_name}...")
            
            # 获取所有物品嵌入
            all_embeddings = await redis.hgetall(key)
            
            if not all_embeddings:
                logger.warning(f"No embeddings found in Redis for model {self.model_name}")
                return False
            
            # 解析嵌入向量
            vectors = []
            item_ids = []
            
            for item_id_str, embedding_bytes in all_embeddings.items():
                try:
                    item_id = int(item_id_str)
                    embedding = pickle.loads(embedding_bytes)
                    
                    # 确保是 numpy 数组
                    if not isinstance(embedding, np.ndarray):
                        continue
                    
                    # 归一化向量（用于余弦相似度）
                    norm = np.linalg.norm(embedding)
                    if norm > 0:
                        embedding = embedding / norm
                    
                    vectors.append(embedding.astype(np.float32))
                    item_ids.append(item_id)
                    
                except Exception as e:
                    logger.error(f"Failed to parse embedding for item {item_id_str}: {e}")
                    continue
            
            if not vectors:
                logger.warning("No valid embeddings found")
                return False
            
            num_vectors = len(vectors)
            logger.info(f"Loaded {num_vectors} embeddings from Redis")
            
            # 转换为 numpy 数组
            vectors_array = np.vstack(vectors).astype(np.float32)
            
            # 创建索引
            self.index = self._create_index(num_vectors)
            
            # 训练索引（IVF 需要训练）
            if isinstance(self.index, faiss.IndexIVFFlat):
                logger.info("Training IVF index...")
                self.index.train(vectors_array)
            
            # 添加向量到索引
            logger.info("Adding vectors to index...")
            self.index.add(vectors_array)
            
            # 构建 ID 映射
            self.id_to_index = {item_id: idx for idx, item_id in enumerate(item_ids)}
            self.index_to_id = {idx: item_id for idx, item_id in enumerate(item_ids)}
            
            logger.info(
                f"FAISS index built successfully: {num_vectors} vectors, "
                f"index type: {self.index_type}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}", exc_info=True)
            return False
    
    def search(
        self, 
        query_vector: np.ndarray, 
        top_k: int,
        exclude_ids: Optional[List[int]] = None
    ) -> List[Tuple[int, float]]:
        """
        搜索相似向量
        
        Args:
            query_vector: 查询向量（已归一化）
            top_k: 返回数量
            exclude_ids: 要排除的物品ID列表
            
        Returns:
            [(item_id, score), ...] 列表，按相似度降序排列
        """
        if self.index is None:
            logger.error("Index not built, call build_index() first")
            return []
        
        try:
            # 确保查询向量是归一化的
            norm = np.linalg.norm(query_vector)
            if norm > 0:
                query_vector = query_vector / norm
            
            # 转换为 float32 并 reshape
            query_vector = query_vector.astype(np.float32).reshape(1, -1)
            
            # 搜索（返回 top_k * 2 以便后续过滤）
            search_k = top_k * 2 if exclude_ids else top_k
            distances, indices = self.index.search(query_vector, search_k)
            
            # 转换为结果列表
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                if idx < 0:  # FAISS 返回 -1 表示无效结果
                    continue
                
                item_id = self.index_to_id.get(idx)
                if item_id is None:
                    continue
                
                # 排除指定ID
                if exclude_ids and item_id in exclude_ids:
                    continue
                
                # 距离转换为相似度分数（内积就是余弦相似度，因为向量已归一化）
                score = float(dist)
                results.append((item_id, score))
                
                if len(results) >= top_k:
                    break
            
            return results
            
        except Exception as e:
            logger.error(f"FAISS search failed: {e}", exc_info=True)
            return []
    
    def batch_search(
        self,
        query_vectors: np.ndarray,
        top_k: int,
        exclude_ids_list: Optional[List[List[int]]] = None
    ) -> List[List[Tuple[int, float]]]:
        """
        批量搜索相似向量
        
        Args:
            query_vectors: 查询向量数组 (n, dim)
            top_k: 每个查询返回数量
            exclude_ids_list: 每个查询要排除的物品ID列表
            
        Returns:
            每个查询的结果列表
        """
        if self.index is None:
            logger.error("Index not built, call build_index() first")
            return [[] for _ in range(len(query_vectors))]
        
        try:
            # 归一化查询向量
            norms = np.linalg.norm(query_vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1  # 避免除零
            query_vectors = query_vectors / norms
            
            # 转换为 float32
            query_vectors = query_vectors.astype(np.float32)
            
            # 批量搜索
            search_k = top_k * 2 if exclude_ids_list else top_k
            distances, indices = self.index.search(query_vectors, search_k)
            
            # 转换结果
            all_results = []
            for i, (dists, idxs) in enumerate(zip(distances, indices)):
                exclude_ids = exclude_ids_list[i] if exclude_ids_list else None
                results = []
                
                for dist, idx in zip(dists, idxs):
                    if idx < 0:
                        continue
                    
                    item_id = self.index_to_id.get(idx)
                    if item_id is None:
                        continue
                    
                    if exclude_ids and item_id in exclude_ids:
                        continue
                    
                    score = float(dist)
                    results.append((item_id, score))
                    
                    if len(results) >= top_k:
                        break
                
                all_results.append(results)
            
            return all_results
            
        except Exception as e:
            logger.error(f"FAISS batch search failed: {e}", exc_info=True)
            return [[] for _ in range(len(query_vectors))]
    
    def get_index_size(self) -> int:
        """获取索引中的向量数量"""
        if self.index is None:
            return 0
        return self.index.ntotal
    
    def save_index(self, filepath: str) -> bool:
        """
        保存索引到文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否成功保存
        """
        try:
            if self.index is None:
                logger.error("No index to save")
                return False
            
            # 保存索引
            faiss.write_index(self.index, filepath)
            
            # 保存ID映射
            mapping_file = filepath + ".mapping"
            with open(mapping_file, 'wb') as f:
                pickle.dump({
                    'id_to_index': self.id_to_index,
                    'index_to_id': self.index_to_id,
                    'model_name': self.model_name
                }, f)
            
            logger.info(f"Index saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save index: {e}", exc_info=True)
            return False
    
    def load_index(self, filepath: str) -> bool:
        """
        从文件加载索引
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否成功加载
        """
        try:
            # 加载索引
            self.index = faiss.read_index(filepath)
            
            # 加载ID映射
            mapping_file = filepath + ".mapping"
            with open(mapping_file, 'rb') as f:
                mapping_data = pickle.load(f)
                self.id_to_index = mapping_data['id_to_index']
                self.index_to_id = mapping_data['index_to_id']
            
            logger.info(f"Index loaded from {filepath}, {self.index.ntotal} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load index: {e}", exc_info=True)
            return False


# 全局索引管理器实例（按模型名称缓存）
_index_managers: Dict[str, FaissIndexManager] = {}


def get_faiss_index_manager(model_name: str = "lightgcn", index_type: str = "IVF") -> FaissIndexManager:
    """
    获取 FAISS 索引管理器实例（单例模式）
    
    Args:
        model_name: 模型名称
        index_type: 索引类型
        
    Returns:
        FaissIndexManager 实例
    """
    key = f"{model_name}_{index_type}"
    
    if key not in _index_managers:
        _index_managers[key] = FaissIndexManager(model_name, index_type)
    
    return _index_managers[key]

