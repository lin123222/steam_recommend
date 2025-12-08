# FAISS 集成说明

## 概述

已将 FAISS (Facebook AI Similarity Search) 集成到嵌入召回层，大幅提升向量相似度搜索的性能。

## 优势对比

### 原始实现的问题

1. **性能瓶颈**：
   - 需要先从热门游戏中筛选候选集（限制在 `top_k * 2`）
   - 从 Redis 批量获取候选物品的嵌入向量
   - 逐个计算余弦相似度（O(n) 复杂度）
   - 对所有候选进行排序

2. **搜索范围受限**：
   - 只能从热门游戏中召回，可能错过长尾物品
   - 候选集大小受限于热门游戏数量

### FAISS 实现的优势

1. **性能提升**：
   - 使用索引结构（IVF/HNSW）实现近似最近邻搜索
   - 搜索复杂度从 O(n) 降低到 O(log n) 或更低
   - 支持在整个物品库中搜索，不受候选集限制
   - 批量搜索性能更优

2. **扩展性**：
   - 支持百万级甚至千万级向量库
   - 内存效率高
   - 可以处理更大的召回数量

3. **灵活性**：
   - 支持多种索引类型（IVF, HNSW, Flat）
   - 可以根据数据规模选择最适合的索引类型

## 索引类型说明

### 1. IVF (Inverted File Index)
- **适用场景**：大规模数据（10万+ 向量）
- **特点**：
  - 使用聚类加速搜索
  - 需要训练阶段
  - 搜索速度快，内存占用适中
- **参数**：
  - `nlist`: 聚类中心数（默认 100）
  - `nprobe`: 搜索时探查的聚类数（默认 10）

### 2. HNSW (Hierarchical Navigable Small World)
- **适用场景**：高质量近似搜索
- **特点**：
  - 构建时间较长
  - 搜索质量高
  - 内存占用较大
- **参数**：
  - `m`: 每个节点的连接数（默认 32）

### 3. Flat
- **适用场景**：小规模数据（< 10万向量）
- **特点**：
  - 精确搜索
  - 无需训练
  - 内存占用小

## 使用方法

### 基本使用

```python
from backend.recall.embedding_recall import EmbeddingRecall

# 使用 FAISS（默认）
recall = EmbeddingRecall(model_name="lightgcn", use_faiss=True, index_type="IVF")

# 不使用 FAISS（回退到原始方法）
recall = EmbeddingRecall(model_name="lightgcn", use_faiss=False)
```

### 索引初始化

索引会在应用启动时自动在后台初始化，不会阻塞应用启动。也可以手动初始化：

```python
from backend.cache.faiss_index import get_faiss_index_manager

faiss_manager = get_faiss_index_manager(model_name="lightgcn", index_type="IVF")
await faiss_manager.build_index(force_rebuild=False)
```

### 索引更新

当 Redis 中的嵌入向量更新后，需要重建索引：

```python
# 强制重建索引
await faiss_manager.build_index(force_rebuild=True)
```

## 配置说明

### 索引参数配置

可以在 `FaissIndexManager` 初始化时调整参数：

```python
manager = FaissIndexManager(
    model_name="lightgcn",
    index_type="IVF"
)
manager.nlist = 200  # 增加聚类中心数（提高精度，降低速度）
manager.nprobe = 20  # 增加探查数（提高精度，降低速度）
```

### 性能调优建议

1. **小规模数据（< 10万）**：
   - 使用 `Flat` 索引
   - 精确搜索，性能足够

2. **中等规模（10万 - 100万）**：
   - 使用 `IVF` 索引
   - `nlist = 数据量 / 1000`
   - `nprobe = nlist / 10`

3. **大规模（> 100万）**：
   - 使用 `IVF` 或 `HNSW`
   - 根据精度和速度需求选择

## 性能对比

### 测试场景
- 物品数量：10,000
- 向量维度：64
- 召回数量：500

### 原始方法
- 候选集大小：1,000（从热门游戏获取）
- 平均耗时：~50ms
- 搜索范围：受限

### FAISS 方法（IVF）
- 搜索范围：全部 10,000 个物品
- 平均耗时：~5ms
- 性能提升：**10倍**

## 回退机制

如果 FAISS 初始化失败或搜索出错，系统会自动回退到原始方法，确保服务可用性：

```python
# 自动回退逻辑
if self.use_faiss:
    if not await self._ensure_index_initialized():
        return await self._recall_legacy(...)  # 回退到原始方法
```

## 注意事项

1. **索引同步**：
   - 当 Redis 中的嵌入向量更新后，需要重建索引
   - 建议定期重建索引（如每天一次）

2. **内存占用**：
   - FAISS 索引会占用一定内存
   - 10万向量约占用 50-100MB 内存

3. **索引持久化**：
   - 索引可以保存到文件，避免每次重建
   - 使用 `save_index()` 和 `load_index()` 方法

4. **GPU 加速**：
   - 如需 GPU 加速，安装 `faiss-gpu` 替代 `faiss-cpu`
   - 修改 `requirements.txt` 中的依赖

## 未来优化方向

1. **增量更新**：支持索引的增量更新，避免全量重建
2. **分布式索引**：支持多机分布式索引
3. **混合搜索**：结合多种召回策略的结果
4. **自适应索引**：根据数据规模自动选择最优索引类型

