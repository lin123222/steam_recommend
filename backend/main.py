"""
FilmSense Backend - 主应用入口
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import logging

from backend.config import settings
from backend.api.v1.api import api_router
from backend.database.connection import init_db, close_db
from backend.cache.redis_client import init_redis, close_redis

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_application() -> FastAPI:
    """创建FastAPI应用"""
    
    app = FastAPI(
        title="FilmSense API",
        description="Steam游戏推荐系统API",
        version="1.0.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    
    # 添加中间件
    setup_middleware(app)
    
    # 添加路由
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    # 添加事件处理器
    setup_event_handlers(app)
    
    # 添加异常处理器
    setup_exception_handlers(app)
    
    return app


def setup_middleware(app: FastAPI) -> None:
    """设置中间件"""
    
    # CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 信任主机中间件
    if not settings.DEBUG:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"]  # 生产环境应该配置具体的主机
        )
    
    # 请求时间中间件
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        
        # 记录慢请求
        if process_time > 1.0:  # 超过1秒的请求
            logger.warning(
                f"Slow request: {request.method} {request.url} took {process_time:.2f}s"
            )
        
        return response


def setup_event_handlers(app: FastAPI) -> None:
    """设置事件处理器"""
    
    @app.on_event("startup")
    async def startup_event():
        """应用启动事件"""
        logger.info("Starting FilmSense Backend...")
        
        # 初始化数据库连接
        await init_db()
        logger.info("Database connection initialized")
        
        # 初始化Redis连接
        await init_redis()
        logger.info("Redis connection initialized")
        
        logger.info("FilmSense Backend started successfully!")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """应用关闭事件"""
        logger.info("Shutting down FilmSense Backend...")
        
        # 关闭数据库连接
        await close_db()
        logger.info("Database connection closed")
        
        # 关闭Redis连接
        await close_redis()
        logger.info("Redis connection closed")
        
        logger.info("FilmSense Backend shutdown complete")


def setup_exception_handlers(app: FastAPI) -> None:
    """设置异常处理器"""
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """全局异常处理器"""
        logger.error(f"Global exception: {exc}", exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "request_id": getattr(request.state, "request_id", None)
            }
        )


# 创建应用实例
app = create_application()


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Welcome to FilmSense API",
        "docs": "/docs",
        "version": "1.0.0"
    }
