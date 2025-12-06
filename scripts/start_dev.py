"""
开发环境启动脚本
"""

import os
import sys
import asyncio
import subprocess
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database.connection import init_db, create_tables
from backend.cache.redis_client import init_redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_environment():
    """检查环境配置"""
    logger.info("Checking environment configuration...")
    
    # 检查.env文件
    env_file = project_root / ".env"
    if not env_file.exists():
        logger.warning(".env file not found, copying from .env.example")
        example_file = project_root / ".env.example"
        if example_file.exists():
            import shutil
            shutil.copy(example_file, env_file)
            logger.info("Please edit .env file with your configuration")
        else:
            logger.error(".env.example file not found")
            return False
    
    # 检查必要的环境变量
    required_vars = [
        "DATABASE_URL",
        "REDIS_URL", 
        "JWT_SECRET_KEY"
    ]
    
    # 加载.env文件
    from dotenv import load_dotenv
    load_dotenv(env_file)
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    logger.info("Environment configuration OK")
    return True


def check_dependencies():
    """检查依赖是否安装"""
    logger.info("Checking dependencies...")
    
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import redis
        import pydantic
        logger.info("All dependencies are installed")
        return True
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.info("Please run: pip install -r requirements.txt")
        return False


async def check_services():
    """检查外部服务连接"""
    logger.info("Checking external services...")
    
    try:
        # 检查数据库连接
        logger.info("Testing database connection...")
        await init_db()
        logger.info("Database connection OK")
        
        # 检查Redis连接
        logger.info("Testing Redis connection...")
        await init_redis()
        logger.info("Redis connection OK")
        
        return True
        
    except Exception as e:
        logger.error(f"Service check failed: {e}")
        return False


async def setup_database():
    """设置数据库"""
    logger.info("Setting up database...")
    
    try:
        # 创建表
        await create_tables()
        logger.info("Database tables created successfully")
        
        return True
        
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        return False


def start_server():
    """启动开发服务器"""
    logger.info("Starting development server...")
    
    # 启动uvicorn服务器
    cmd = [
        "uvicorn",
        "backend.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "info"
    ]
    
    try:
        subprocess.run(cmd, cwd=project_root)
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}")


async def main():
    """主函数"""
    logger.info("Starting FilmSense Backend Development Server...")
    
    # 1. 检查环境
    if not check_environment():
        logger.error("Environment check failed")
        return
    
    # 2. 检查依赖
    if not check_dependencies():
        logger.error("Dependencies check failed")
        return
    
    # 3. 检查服务
    if not await check_services():
        logger.error("Services check failed")
        logger.info("Please make sure PostgreSQL and Redis are running")
        return
    
    # 4. 设置数据库
    if not await setup_database():
        logger.error("Database setup failed")
        return
    
    logger.info("All checks passed! Starting server...")
    logger.info("Server will be available at: http://localhost:8000")
    logger.info("API documentation: http://localhost:8000/docs")
    logger.info("Press Ctrl+C to stop the server")
    
    # 5. 启动服务器
    start_server()


if __name__ == "__main__":
    asyncio.run(main())
