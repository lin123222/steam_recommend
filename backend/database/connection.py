"""
数据库连接管理
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from backend.config import get_database_url, settings
from backend.logging_config import get_logger

logger = get_logger(__name__)

# 创建基础模型类
Base = declarative_base()

# 全局变量
engine = None
async_session_maker = None


async def init_db() -> None:
    """初始化数据库连接"""
    global engine, async_session_maker
    
    database_url = get_database_url()
    # 脱敏数据库URL（隐藏密码）
    safe_url = database_url.split('@')[1] if '@' in database_url else database_url
    logger.info(f"Connecting to database: {safe_url}")
    
    try:
        # 创建异步引擎
        engine = create_async_engine(
            database_url,
            echo=settings.DEBUG,  # 开发环境下显示SQL
            pool_size=settings.MAX_CONNECTIONS_COUNT,
            max_overflow=20,
            pool_pre_ping=True,  # 连接前验证
            pool_recycle=3600,   # 1小时后回收连接
        )
        
        # 注意：异步引擎的事件监听需要使用 sync_engine
        # 这里简化处理，慢查询日志在应用层记录
        if settings.DEBUG:
            logger.debug("SQL query logging enabled (DEBUG mode)")
        
        # 创建会话工厂
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        logger.info(f"Database connection initialized successfully (pool_size={settings.MAX_CONNECTIONS_COUNT})")
        
    except Exception as e:
        logger.error(f"Failed to initialize database connection: {e}", exc_info=True)
        raise


async def close_db() -> None:
    """关闭数据库连接"""
    global engine
    
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话
    
    Yields:
        数据库会话
    """
    if not async_session_maker:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """创建数据库表"""
    if not engine:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    # 导入所有模型以确保它们被注册
    from backend.database import models  # noqa
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")


async def drop_tables() -> None:
    """删除数据库表（仅用于测试）"""
    if not engine:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    
    # 导入所有模型
    from backend.database import models  # noqa
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    logger.info("Database tables dropped successfully")
