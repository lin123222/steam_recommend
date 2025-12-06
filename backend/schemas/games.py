"""
游戏相关的 Pydantic 模型
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import date


class GameBase(BaseModel):
    """游戏基础模型"""
    app_id: str = Field(..., description="Steam App ID")
    app_name: str = Field(..., description="游戏名称")
    genres: List[str] = Field(default_factory=list, description="游戏品类")
    tags: List[str] = Field(default_factory=list, description="游戏标签")
    price: Optional[float] = Field(None, description="价格")
    discount_price: Optional[float] = Field(None, description="折扣价")
    developer: Optional[str] = Field(None, description="开发商")
    publisher: Optional[str] = Field(None, description="发行商")
    release_date: Optional[str] = Field(None, description="发布日期")


class GameListItem(GameBase):
    """游戏列表项模型（用于发现页）"""
    specs: List[str] = Field(default_factory=list, description="游戏特性")
    early_access: bool = Field(False, description="是否抢先体验")
    
    class Config:
        from_attributes = True


class GameDetail(GameBase):
    """游戏详情模型"""
    description: Optional[str] = Field(None, description="详细描述")
    short_description: Optional[str] = Field(None, description="简短描述")
    specs: List[str] = Field(default_factory=list, description="游戏特性")
    languages: List[str] = Field(default_factory=list, description="支持语言")
    discount_percent: int = Field(0, description="折扣百分比")
    store_url: Optional[str] = Field(None, description="商店链接")
    reviews_url: Optional[str] = Field(None, description="评测链接")
    early_access: bool = Field(False, description="是否抢先体验")
    
    class Config:
        from_attributes = True


class GameListResponse(BaseModel):
    """游戏列表响应模型"""
    games: List[GameListItem]
    pagination: dict = Field(..., description="分页信息")
    filters_applied: dict = Field(default_factory=dict, description="已应用的筛选条件")


class GenreItem(BaseModel):
    """品类项模型"""
    id: str
    name: str
    count: int = Field(0, description="该品类的游戏数量")


class GenreResponse(BaseModel):
    """品类列表响应"""
    genres: List[GenreItem]


class TagItem(BaseModel):
    """标签项模型"""
    id: str
    name: str
    count: int = Field(0, description="该标签的游戏数量")


class TagResponse(BaseModel):
    """标签列表响应"""
    tags: List[TagItem]


class GameRecommendation(GameBase):
    """推荐游戏模型（包含推荐相关字段）"""
    match_score: int = Field(..., ge=0, le=100, description="匹配度分数")
    recommend_reason: str = Field(..., description="推荐理由")
    explanation: dict = Field(..., description="推荐解释")
    
    class Config:
        from_attributes = True
