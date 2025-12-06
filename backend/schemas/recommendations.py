"""
推荐相关的Pydantic模式
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, validator


class RecommendationRequest(BaseModel):
    """推荐请求模式"""
    user_id: int
    topk: Optional[int] = 10
    algorithm: Optional[str] = "auto"  # auto, embedding, popularity, content
    
    @validator('topk')
    def validate_topk(cls, v):
        if v is not None:
            if v < 1:
                raise ValueError('topk must be at least 1')
            if v > 100:
                raise ValueError('topk must be at most 100')
        return v


class GameInfo(BaseModel):
    """游戏信息模式"""
    product_id: int
    title: str
    genres: List[str] = []
    tags: List[str] = []
    developer: Optional[str] = None
    publisher: Optional[str] = None
    metascore: Optional[int] = None
    sentiment: Optional[str] = None
    release_date: Optional[str] = None
    price: Optional[float] = None
    score: float  # 推荐分数


class RecommendationResponse(BaseModel):
    """推荐响应模式"""
    user_id: int
    recommendations: List[GameInfo]
    algorithm: str
    timestamp: int
    total_time_ms: float
    recall_time_ms: Optional[float] = None
    ranking_time_ms: Optional[float] = None


class ExplanationRequest(BaseModel):
    """推荐解释请求模式"""
    user_id: int
    product_id: int


class InfluentialGame(BaseModel):
    """影响推荐的游戏"""
    product_id: int
    title: str
    weight: float


class ExplanationResponse(BaseModel):
    """推荐解释响应模式"""
    product_id: int
    explanation: str
    influential_games: List[InfluentialGame] = []
    algorithm: str


class InteractionData(BaseModel):
    """交互数据模式"""
    user_id: int
    product_id: int
    timestamp: Optional[int] = None
    play_hours: Optional[float] = 0.0
    early_access: Optional[bool] = False


class InteractionResponse(BaseModel):
    """交互响应模式"""
    status: str
    message: str
    interaction_id: Optional[int] = None


class UserReviewCreate(BaseModel):
    """用户评价创建模式"""
    user_id: int
    product_id: int
    rating: float
    review_text: Optional[str] = None
    
    @validator('rating')
    def validate_rating(cls, v):
        if v < 0 or v > 5:
            raise ValueError('Rating must be between 0 and 5')
        return v


class UserReviewResponse(BaseModel):
    """用户评价响应模式"""
    review_id: int
    user_id: int
    product_id: int
    rating: float
    review_text: Optional[str] = None
    created_at: str


class GameDetailResponse(BaseModel):
    """游戏详情响应模式"""
    product_id: int
    title: str
    app_name: Optional[str] = None
    genres: List[str] = []
    tags: List[str] = []
    developer: Optional[str] = None
    publisher: Optional[str] = None
    metascore: Optional[int] = None
    sentiment: Optional[str] = None
    release_date: Optional[str] = None
    price: Optional[float] = None
    user_rating: Optional[float] = None  # 用户对该游戏的评分


class FeedbackData(BaseModel):
    """用户反馈数据"""
    user_id: int
    product_id: int
    feedback_type: str  # 'like', 'dislike', 'not_interested'
    recommendation_id: Optional[str] = None
    
    @validator('feedback_type')
    def validate_feedback_type(cls, v):
        allowed_types = ['like', 'dislike', 'not_interested']
        if v not in allowed_types:
            raise ValueError(f'feedback_type must be one of {allowed_types}')
        return v


class RecommendationStats(BaseModel):
    """推荐统计信息"""
    total_requests: int
    avg_response_time_ms: float
    cache_hit_rate: float
    algorithm_distribution: Dict[str, int]
    error_rate: float
