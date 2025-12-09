"""
FilmSense Backend - 主应用入口
"""

import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings
from backend.api.v1.api import api_router
from backend.database.connection import init_db, close_db
from backend.cache.redis_client import init_redis, close_redis
from backend.cache.faiss_index import get_faiss_index_manager
from backend.logging_config import setup_logging, get_logger
from backend.utils.logger import log_request, log_slow_request
from backend.tasks.demo_import import main as demo_import_main

# 初始化日志系统
setup_logging(
    log_dir=settings.LOG_DIR,
    log_level=settings.LOG_LEVEL,
    enable_file_logging=settings.ENABLE_FILE_LOGGING,
    enable_console_logging=settings.ENABLE_CONSOLE_LOGGING
)

logger = get_logger(__name__)


async def _init_faiss_index_background(faiss_manager):
    """后台初始化 FAISS 索引"""
    try:
        logger.info("Initializing FAISS index in background...")
        success = await faiss_manager.build_index(force_rebuild=False)
        if success:
            logger.info(
                f"FAISS index initialized successfully: "
                f"{faiss_manager.get_index_size()} vectors"
            )
        else:
            logger.warning("FAISS index initialization failed, will use legacy method")
    except Exception as e:
        logger.error(f"Background FAISS index initialization failed: {e}")


async def _compute_user_profiles_background():
    """后台计算用户画像"""
    try:
        # 等待一段时间，确保其他初始化完成
        import asyncio
        await asyncio.sleep(5)
        
        logger.info("Starting user profile computation in background...")
        
        from backend.tasks.compute_user_profiles import UserProfileComputer
        
        computer = UserProfileComputer()
        computer.load_embeddings()
        await computer.load_game_metadata()
        
        # 计算用户画像（与 demo_import 的 DEMO_USER_COUNT 保持一致）
        # 生产环境可以去掉 limit 或设置为 None 来处理所有用户
        stats = await computer.compute_all_users(limit=20)  # 与 demo_import 一致
        
        logger.info(
            f"User profile computation completed: "
            f"total={stats['total']}, success={stats['success']}, failed={stats['failed']}"
        )
    except Exception as e:
        logger.error(f"Background user profile computation failed: {e}")


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
    
    # 请求ID中间件
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """为每个请求添加唯一ID"""
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    
    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录所有HTTP请求"""
        start_time = time.time()
        request_id = getattr(request.state, "request_id", None)
        
        # 获取客户端IP
        client_ip = request.client.host if request.client else None
        if "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        
        # 获取用户ID（如果已认证）
        user_id = None
        if hasattr(request.state, "user_id"):
            user_id = request.state.user_id
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000  # 转换为毫秒
            
            # 添加处理时间头
            response.headers["X-Process-Time"] = f"{process_time:.2f}"
            
            # 记录请求日志
            log_request(
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration_ms=process_time,
                user_id=user_id,
                ip=client_ip,
                request_id=request_id,
                query_params=str(request.query_params) if request.query_params else None
            )
            
            # 记录慢请求
            log_slow_request(
                method=request.method,
                path=str(request.url.path),
                duration_ms=process_time,
                threshold=settings.SLOW_REQUEST_THRESHOLD * 1000,
                user_id=user_id,
                request_id=request_id
            )
            
            return response
            
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                exc_info=True,
                extra={
                    'method': request.method,
                    'path': str(request.url.path),
                    'duration_ms': process_time,
                    'user_id': user_id,
                    'ip': client_ip,
                    'request_id': request_id
                }
            )
            raise


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
        
        # 后台导入 demo 向量并构建索引（不阻塞启动）
        import asyncio
        asyncio.create_task(demo_import_main())

        # 初始化 FAISS 索引（后台异步初始化，不阻塞启动）
        try:
            faiss_manager = get_faiss_index_manager(model_name="lightgcn", index_type="IVF")
            # 在后台任务中初始化索引，避免阻塞应用启动
            asyncio.create_task(_init_faiss_index_background(faiss_manager))
        except Exception as e:
            logger.warning(f"Failed to initialize FAISS index manager: {e}")
        
        # 后台计算用户画像（不阻塞启动）
        asyncio.create_task(_compute_user_profiles_background())
        
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
        request_id = getattr(request.state, "request_id", None)
        client_ip = request.client.host if request.client else None
        
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
            exc_info=True,
            extra={
                'method': request.method,
                'path': str(request.url.path),
                'ip': client_ip,
                'request_id': request_id
            }
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "request_id": request_id
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
