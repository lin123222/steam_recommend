"""
用户游戏库相关的 Pydantic 模型
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class LibraryGameBase(BaseModel):
    """游戏库游戏基础模型"""
    app_id: str = Field(..., description="Steam App ID")
    app_name: str = Field(..., description="游戏名称")
    genres: List[str] = Field(default_factory=list, description="游戏品类")
    tags: List[str] = Field(default_factory=list, description="游戏标签")


class LibraryGame(LibraryGameBase):
    """游戏库游戏模型（包含游玩数据）"""
    playtime_hours: float = Field(0.0, description="游玩时长（小时）")
    last_played_at: Optional[str] = Field(None, description="最后游玩时间")
    last_played_relative: Optional[str] = Field(None, description="相对时间描述")
    
    is_installed: bool = Field(False, description="是否已安装")
    is_favorite: bool = Field(False, description="是否收藏")
    
    achievement_progress: int = Field(0, ge=0, le=100, description="成就完成百分比")
    achievements_unlocked: int = Field(0, description="已解锁成就数")
    achievements_total: int = Field(0, description="总成就数")
    
    purchase_date: Optional[str] = Field(None, description="购买日期")
    purchase_price: Optional[float] = Field(None, description="购买价格")
    
    class Config:
        from_attributes = True


class LibrarySummary(BaseModel):
    """游戏库统计摘要"""
    total_games: int = Field(0, description="总游戏数")
    installed_count: int = Field(0, description="已安装游戏数")
    favorites_count: int = Field(0, description="收藏游戏数")


class LibraryResponse(BaseModel):
    """游戏库响应模型"""
    games: List[LibraryGame]
    summary: LibrarySummary
    pagination: dict = Field(..., description="分页信息")


class ToggleFavoriteRequest(BaseModel):
    """切换收藏请求模型"""
    user_id: str = Field(..., description="用户ID")
    game_id: str = Field(..., description="游戏ID (app_id)")


class ToggleFavoriteResponse(BaseModel):
    """切换收藏响应模型"""
    success: bool = Field(..., description="是否成功")
    is_liked: bool = Field(..., description="当前收藏状态")
    message: Optional[str] = Field(None, description="消息")
