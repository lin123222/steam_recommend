"""
API v1 路由汇总
"""

from fastapi import APIRouter

from backend.api.v1.endpoints import auth, recommendations, users, interactions, games, library

api_router = APIRouter()

# 包含各个模块的路由
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/user", tags=["users"])
api_router.include_router(library.router, prefix="/user", tags=["library"])  # 游戏库路由也在 /user 下
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(interactions.router, prefix="/interactions", tags=["interactions"])
api_router.include_router(games.router, prefix="/games", tags=["games"])

# 添加交互路由别名（兼容前端调用 /api/v1/interact）
# 将 interactions.router 的 /interact 端点也注册到根路径
api_router.include_router(interactions.router, tags=["interactions-alias"])
