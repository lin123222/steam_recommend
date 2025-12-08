"""
批量测试前 N 个用户的推荐结果。

用法：
    python -m backend.tasks.test_recommendations

环境变量（可选）：
    USER_MAP_PATH  默认 D:\\学科实践\\exported_with_id\\user_id_map.json
    TOP_K          默认 10
    USER_COUNT     默认 20
    MODEL_NAME     默认 lightgcn
"""

import asyncio
import json
import os
from typing import Dict, List

import backend.database.connection as db_conn
from backend.api.pipeline import RecommendationPipeline
from backend.database.models import GameMetadata
from sqlalchemy import select


USER_MAP_PATH = os.getenv("USER_MAP_PATH", r"D:\学科实践\exported_with_id\user_id_map.json")
TOP_K = int(os.getenv("TOP_K", "10"))
USER_COUNT = int(os.getenv("USER_COUNT", "20"))
MODEL_NAME = os.getenv("MODEL_NAME", "lightgcn")


def _load_user_ids(path: str, count: int) -> List[int]:
    with open(path, "r", encoding="utf-8") as f:
        data: Dict[str, str] = json.load(f)
    ids = []
    for k in sorted(data.keys(), key=lambda x: int(x)):
        if k == "0":
            continue  # [PAD]
        uid = data[k]
        if uid == "[PAD]":
            continue
        try:
            ids.append(int(uid))
        except ValueError:
            continue
        if len(ids) >= count:
            break
    return ids


async def fetch_metadata(session, product_ids: List[int]) -> Dict[int, GameMetadata]:
    if not product_ids:
        return {}
    stmt = select(GameMetadata).where(GameMetadata.product_id.in_(product_ids))
    result = await session.execute(stmt)
    return {g.product_id: g for g in result.scalars().all()}


async def main():
    await db_conn.init_db()
    # 推荐依赖 Redis/FAISS，需确保你已运行 demo_import 或 import_game_data
    from backend.cache.redis_client import init_redis
    await init_redis()

    user_ids = _load_user_ids(USER_MAP_PATH, USER_COUNT)
    print(f"Loaded test users: {user_ids}")

    pipeline = RecommendationPipeline()

    async with db_conn.async_session_maker() as session:
        for uid in user_ids:
            result = await pipeline.recommend(
                user_id=uid,
                top_k=TOP_K,
                algorithm="embedding",
                ranking_strategy="default",
            )
            rec_ids = result.get("recommendations", [])
            meta_map = await fetch_metadata(session, rec_ids)

            print(f"\nUser {uid} -> {len(rec_ids)} recs (alg={result.get('algorithm')})")
            for pid in rec_ids:
                meta = meta_map.get(pid)
                title = meta.title if meta else f"Game {pid}"
                print(f"  {pid}\t{title}")


if __name__ == "__main__":
    asyncio.run(main())

