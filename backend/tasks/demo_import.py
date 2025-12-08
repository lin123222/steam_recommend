"""
Demo 导入脚本：导入前 20 个用户向量 + 全量物品向量，并重建 FAISS 索引。

使用说明：
    python -m backend.tasks.demo_import

可配置项（环境变量，可选）：
    DEMO_USER_COUNT      默认 20
    USER_EMB_PATH        默认 D:\\学科实践\\exported_with_id\\user_embeddings.npy
    ITEM_EMB_PATH        默认 D:\\学科实践\\exported_with_id\\item_embeddings.npy
    USER_MAP_PATH        默认 D:\\学科实践\\exported_with_id\\user_id_map.json
    ITEM_MAP_PATH        默认 D:\\学科实践\\exported_with_id\\item_id_map.json
    MODEL_NAME           默认 lightgcn
"""

import asyncio
import json
import os
import pickle
import logging
from typing import Dict, List

import numpy as np

from backend.cache.feature_store import FeatureStore
from backend.cache.redis_client import init_redis
from backend.cache.faiss_index import get_faiss_index_manager

logger = logging.getLogger(__name__)


# 默认路径（可通过环境变量覆盖）
USER_EMB_PATH = os.getenv("USER_EMB_PATH", r"D:\学科实践\exported_with_id\user_embeddings.npy")
ITEM_EMB_PATH = os.getenv("ITEM_EMB_PATH", r"D:\学科实践\exported_with_id\item_embeddings.npy")
USER_MAP_PATH = os.getenv("USER_MAP_PATH", r"D:\学科实践\exported_with_id\user_id_map.json")
ITEM_MAP_PATH = os.getenv("ITEM_MAP_PATH", r"D:\学科实践\exported_with_id\item_id_map.json")

DEMO_USER_COUNT = int(os.getenv("DEMO_USER_COUNT", "20"))
MODEL_NAME = os.getenv("MODEL_NAME", "lightgcn")


def _load_id_map(path: str) -> Dict[int, str]:
    """加载索引->原始ID 映射，key 为 int。"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {int(k): v for k, v in data.items()}


def _select_demo_users(id_map: Dict[int, str], count: int) -> List[int]:
    """
    选择前 count 个真实用户的索引（跳过 index 0 的 [PAD]）。
    返回值是 numpy 数组行号（即内部索引）。
    """
    selected = []
    for idx in sorted(id_map.keys()):
        if idx == 0:  # 跳过 PAD
            continue
        if id_map[idx] == "[PAD]":
            continue
        selected.append(idx)
        if len(selected) >= count:
            break
    return selected


async def main() -> None:
    await init_redis()
    fs = FeatureStore()

    logger.info("Loading id maps...")
    user_id_map = _load_id_map(USER_MAP_PATH)
    item_id_map = _load_id_map(ITEM_MAP_PATH)

    logger.info("Selecting demo users (count=%d)...", DEMO_USER_COUNT)
    demo_user_indices = _select_demo_users(user_id_map, DEMO_USER_COUNT)
    logger.info("Selected indices: %s", demo_user_indices)

    logger.info("Loading embeddings...")
    user_emb = np.load(USER_EMB_PATH)  # shape: (N_user, dim)
    item_emb = np.load(ITEM_EMB_PATH)  # shape: (N_item, dim)

    # 构造用户字典：原始ID -> 向量
    user_dict: Dict[int, np.ndarray] = {}
    for idx in demo_user_indices:
        orig_id = user_id_map[idx]
        try:
            uid = int(orig_id)
        except ValueError:
            logger.warning("Skip non-int user id: %s", orig_id)
            continue
        user_dict[uid] = user_emb[idx]

    # 构造物品字典：原始ID -> 向量（全量）
    item_dict: Dict[int, np.ndarray] = {}
    for idx, orig_id in item_id_map.items():
        if orig_id == "[PAD]":
            continue
        try:
            iid = int(orig_id)
        except ValueError:
            logger.warning("Skip non-int item id: %s", orig_id)
            continue
        item_dict[iid] = item_emb[idx]

    logger.info("Writing embeddings to Redis... (users=%d, items=%d)", len(user_dict), len(item_dict))
    await fs.cache_embeddings(
        model_name=MODEL_NAME,
        user_embeddings=user_dict,
        item_embeddings=item_dict,
    )

    logger.info("Building FAISS index...")
    manager = get_faiss_index_manager(model_name=MODEL_NAME, index_type="IVF")
    success = await manager.build_index(force_rebuild=True)
    if success:
        logger.info("FAISS index built, size=%d", manager.get_index_size())
    else:
        logger.warning("FAISS index build failed.")

    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())

