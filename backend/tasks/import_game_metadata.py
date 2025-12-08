"""
导入游戏原始元数据到数据库的脚本。

功能：
- 逐行读取原始游戏数据文件（本地为 `steam_games copy.json`，每行一个 Python 风格字典）。
- 可选读取 item_id_map.json，仅导入在映射内的游戏，保证与向量 ID 对齐。
- 批量插入到 `game_metadata` 表（如已存在同 product_id 则跳过）。

使用示例：
    python -m backend.tasks.import_game_metadata

环境变量（可选）：
    GAME_JSON_PATH   默认 d:\\学科实践\\steam_games copy.json
    ITEM_MAP_PATH    如果提供，则仅导入映射内的 product_id（索引->原始ID）
    DB_BATCH_SIZE    默认 1000
"""

import asyncio
import ast
import json
import logging
import os
from typing import Dict, Iterable, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.mysql import insert as mysql_insert

import backend.database.connection as db_conn
from backend.database.models import GameMetadata

logger = logging.getLogger(__name__)

GAME_JSON_PATH = os.getenv("GAME_JSON_PATH", r"d:\学科实践\steam_games copy.json")
ITEM_MAP_PATH = os.getenv("ITEM_MAP_PATH", "")
DB_BATCH_SIZE = int(os.getenv("DB_BATCH_SIZE", "1000"))
UPSERT_EXISTING = os.getenv("UPSERT_EXISTING", "").lower() not in ("", "0", "false")


def _load_item_map(path: str) -> Set[int]:
    """加载 item_id_map，返回允许导入的 product_id 集合。"""
    if not path:
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ids = set()
    for _, orig in data.items():
        if orig == "[PAD]":
            continue
        try:
            ids.add(int(orig))
        except (TypeError, ValueError):
            continue
    logger.info("Loaded %d ids from item map %s", len(ids), path)
    return ids


def _to_comma_str(value: Optional[Iterable[str]]) -> Optional[str]:
    if not value:
        return None
    return ",".join([str(v).strip() for v in value if str(v).strip()])


def _parse_price(raw_price) -> Optional[float]:
    if raw_price is None:
        return None
    # 字符串里含 Free/Free to Play 等视为 0
    if isinstance(raw_price, str):
        lower = raw_price.lower()
        if "free" in lower:
            return 0.0
        try:
            return float(raw_price)
        except ValueError:
            return None
    try:
        return float(raw_price)
    except (TypeError, ValueError):
        return None


def _parse_metascore(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _normalize_release_date(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # 截断以避免超过 DB 长度 (VARCHAR(20) 左右)
    return s[:20]


def _normalize_record(raw: Dict, allowed_ids: Set[int]) -> Optional[Dict]:
    """
    将原始行转换为 GameMetadata 可接受的字段字典。
    如果不在 allowed_ids 且 allowed_ids 非空，则返回 None。
    """
    pid_raw = raw.get("id")
    if pid_raw is None:
        return None
    try:
        product_id = int(pid_raw)
    except (TypeError, ValueError):
        return None

    if allowed_ids and product_id not in allowed_ids:
        return None

    title = raw.get("title") or raw.get("app_name") or str(product_id)
    app_name = raw.get("app_name") or title
    genres = _to_comma_str(raw.get("genres"))
    tags = _to_comma_str(raw.get("tags"))
    developer = raw.get("developer")
    publisher = raw.get("publisher")
    metascore = _parse_metascore(raw.get("metascore"))
    sentiment = raw.get("sentiment")
    release_date = _normalize_release_date(raw.get("release_date"))
    price = _parse_price(raw.get("price"))
    discount_price = _parse_price(raw.get("discount_price"))
    description = raw.get("description")
    short_description = raw.get("short_description")
    specs = _to_comma_str(raw.get("specs"))
    url = raw.get("url")
    reviews_url = raw.get("reviews_url")
    early_access = bool(raw.get("early_access")) if raw.get("early_access") is not None else None

    return {
        "product_id": product_id,
        "title": title,
        "app_name": app_name,
        "genres": genres,
        "tags": tags,
        "developer": developer,
        "publisher": publisher,
        "metascore": metascore,
        "sentiment": sentiment,
        "release_date": release_date,
        "price": price,
        "discount_price": discount_price,
        "description": description,
        "short_description": short_description,
        "specs": specs,
        "url": url,
        "reviews_url": reviews_url,
        "early_access": early_access,
    }


async def _load_existing_ids(session: AsyncSession) -> Set[int]:
    stmt = select(GameMetadata.product_id)
    result = await session.execute(stmt)
    return set(result.scalars().all())


async def _bulk_insert(session: AsyncSession, rows: List[Dict]) -> int:
    if not rows:
        return 0
    session.add_all([GameMetadata(**row) for row in rows])
    await session.commit()
    return len(rows)


async def _bulk_upsert(session: AsyncSession, rows: List[Dict]) -> int:
    """
    使用 MySQL ON DUPLICATE KEY UPDATE 进行批量插入/更新。
    """
    if not rows:
        return 0
    stmt = mysql_insert(GameMetadata).values(rows)
    update_cols = {
        c.name: stmt.inserted[c.name]
        for c in GameMetadata.__table__.columns
        if c.name != "product_id"
    }
    upsert_stmt = stmt.on_duplicate_key_update(**update_cols)
    await session.execute(upsert_stmt)
    await session.commit()
    return len(rows)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting import from %s", GAME_JSON_PATH)
    await db_conn.init_db()

    allowed_ids = _load_item_map(ITEM_MAP_PATH)

    async with db_conn.async_session_maker() as session:
        existing_ids: Set[int] = set()
        if not UPSERT_EXISTING:
            existing_ids = await _load_existing_ids(session)
            logger.info("Existing rows in game_metadata: %d", len(existing_ids))

        to_write: List[Dict] = []
        inserted = 0
        updated = 0
        skipped_existing = 0
        skipped_filter = 0
        parse_errors = 0

        with open(GAME_JSON_PATH, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = ast.literal_eval(line)
                except Exception:
                    parse_errors += 1
                    continue

                record = _normalize_record(raw, allowed_ids)
                if not record:
                    skipped_filter += 1
                    continue

                pid = record["product_id"]
                if not UPSERT_EXISTING and pid in existing_ids:
                    skipped_existing += 1
                    continue

                to_write.append(record)

                if len(to_write) >= DB_BATCH_SIZE:
                    if UPSERT_EXISTING:
                        updated += await _bulk_upsert(session, to_write)
                    else:
                        inserted += await _bulk_insert(session, to_write)
                        existing_ids.update([r["product_id"] for r in to_write])
                    to_write = []

        if to_write:
            if UPSERT_EXISTING:
                updated += await _bulk_upsert(session, to_write)
            else:
                inserted += await _bulk_insert(session, to_write)

        logger.info(
            "Import finished. inserted=%d, updated_or_upserted=%d, skipped_existing=%d, skipped_filter_or_invalid=%d, parse_errors=%d",
            inserted,
            updated,
            skipped_existing,
            skipped_filter,
            parse_errors,
        )


if __name__ == "__main__":
    asyncio.run(main())

