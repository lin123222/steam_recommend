"""
数据库初始化脚本
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database.connection import init_db, create_tables
from backend.cache.redis_client import init_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database():
    """初始化数据库"""
    try:
        logger.info("Initializing database connection...")
        await init_db()
        
        logger.info("Creating database tables...")
        await create_tables()
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def init_cache():
    """初始化缓存"""
    try:
        logger.info("Initializing Redis connection...")
        await init_redis()
        
        logger.info("Redis initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        raise


async def main():
    """主函数"""
    try:
        await init_database()
        await init_cache()
        logger.info("All services initialized successfully!")
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
