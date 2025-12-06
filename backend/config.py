"""
应用配置管理
"""

import os
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""
    
    # API配置
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # 日志配置
    LOG_DIR: Optional[str] = None  # 日志目录，默认为项目根目录下的 logs
    ENABLE_FILE_LOGGING: bool = True
    ENABLE_CONSOLE_LOGGING: bool = True
    SLOW_REQUEST_THRESHOLD: float = 1.0  # 慢请求阈值（秒）
    SLOW_QUERY_THRESHOLD: float = 0.5  # 慢查询阈值（秒）
    
    # 数据库配置
    DATABASE_URL: Optional[str] = None  # 如果设置了 DATABASE_URL，将优先使用，忽略其他 DB_* 配置
    DB_TYPE: str = "postgresql"  # postgresql 或 mysql
    DB_HOST: str = "localhost"
    DB_PORT: Optional[int] = None  # 如果未设置，将根据 DB_TYPE 自动选择默认端口
    DB_NAME: str = "filmsense"
    DB_USER: str = "user"
    DB_PASSWORD: str = "password"
    
    # Redis配置
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 20
    
    # JWT配置
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"  # 开发环境默认值，生产环境必须修改
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Triton配置
    TRITON_URL: str = "localhost:8001"
    
    # CORS配置
    ALLOWED_ORIGINS: List[str] = ["*"]
    
    # 连接池配置
    MAX_CONNECTIONS_COUNT: int = 10
    MIN_CONNECTIONS_COUNT: int = 10
    
    # 推荐配置
    DEFAULT_TOPK: int = 10
    MAX_TOPK: int = 100
    CACHE_TTL_SECONDS: int = 3600
    
    # 召回配置
    RECALL_SIZE: int = 500
    EMBEDDING_DIM: int = 64
    MAX_SEQUENCE_LENGTH: int = 50
    
    # 业务规则配置
    MAX_SAME_DEVELOPER: int = 2
    MAX_SAME_GENRE: int = 3
    MIN_INTERACTION_FOR_EMBEDDING: int = 5
    MIN_INTERACTION_FOR_CONTENT: int = 3
    
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }


# 全局配置实例
settings = Settings()


def get_database_url() -> str:
    """
    获取数据库连接URL
    
    优先级：
    1. 如果设置了 DATABASE_URL，直接使用（忽略其他 DB_* 配置）
    2. 否则根据 DB_TYPE 和 DB_* 配置构建连接字符串
    """
    # 如果设置了 DATABASE_URL，优先使用
    if settings.DATABASE_URL:
        return settings.DATABASE_URL

    # 根据 DB_TYPE 选择数据库类型和默认端口
    db_type = settings.DB_TYPE.lower()
    default_port = 3306 if db_type == "mysql" else 5432
    db_port = settings.DB_PORT if settings.DB_PORT is not None else default_port

    if db_type == "mysql":
        return (
            f"mysql+aiomysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
            f"@{settings.DB_HOST}:{db_port}/{settings.DB_NAME}"
        )
    else:  # 默认使用 PostgreSQL
        return (
            f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}"
            f"@{settings.DB_HOST}:{db_port}/{settings.DB_NAME}"
        )


def get_redis_url() -> str:
    """获取Redis连接URL"""
    if settings.REDIS_URL:
        return settings.REDIS_URL
    
    return f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
