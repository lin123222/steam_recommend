"""
用户画像相关的 Pydantic 模型
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class GamerDNAStat(BaseModel):
    """Gamer DNA 单项统计"""
    name: str = Field(..., description="属性名称")
    value: int = Field(..., ge=0, le=100, description="属性值")
    max: int = Field(100, description="最大值")


class GamerDNA(BaseModel):
    """Gamer DNA 雷达图数据"""
    description: str = Field("你的游戏基因分析", description="描述")
    stats: List[GamerDNAStat] = Field(..., description="6维属性数据")
    primary_type: str = Field(..., description="主要类型")
    secondary_type: str = Field(..., description="次要类型")


class BentoStats(BaseModel):
    """Bento Box 统计卡片数据"""
    total_playtime_hours: float = Field(0.0, description="总游玩时长（小时）")
    games_owned: int = Field(0, description="拥有游戏数")
    library_value: float = Field(0.0, description="游戏库总价值")
    achievements_unlocked: int = Field(0, description="已解锁成就数")
    perfect_games: int = Field(0, description="100%完成的游戏数")
    avg_session_minutes: int = Field(0, description="平均游戏时长（分钟）")


class RecentActivity(BaseModel):
    """最近活动"""
    last_played_game_id: Optional[str] = Field(None, description="最后游玩的游戏ID")
    last_played_at: Optional[str] = Field(None, description="最后游玩时间")


class UserProfileResponse(BaseModel):
    """用户画像完整响应"""
    user_id: str = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    level: int = Field(1, description="等级")
    exp: int = Field(0, description="经验值")
    exp_to_next_level: int = Field(1000, description="升级所需经验")
    member_since: Optional[str] = Field(None, description="注册日期")
    
    gamer_dna: GamerDNA = Field(..., description="Gamer DNA 数据")
    bento_stats: BentoStats = Field(..., description="Bento 统计数据")
    favorite_genres: List[str] = Field(default_factory=list, description="喜爱品类")
    recent_activity: RecentActivity = Field(..., description="最近活动")
    
    class Config:
        from_attributes = True
