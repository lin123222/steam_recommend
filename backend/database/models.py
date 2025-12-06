"""
SQLAlchemy数据库模型
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, BigInteger, Boolean, 
    Text, DateTime, Date, Numeric, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.database.connection import Base


class User(Base):
    """用户表"""
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 关系
    interactions = relationship("UserInteraction", back_populates="user", cascade="all, delete-orphan")
    reviews = relationship("UserReview", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.user_id}, username='{self.username}')>"


class UserInteraction(Base):
    """用户交互表"""
    __tablename__ = 'user_interactions'
    
    interaction_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    product_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False)  # Unix时间戳
    play_hours = Column(Float, default=0.0)
    early_access = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="interactions")
    
    # 索引
    __table_args__ = (
        Index('idx_user_time', 'user_id', 'timestamp'),
        Index('idx_product', 'product_id'),
    )
    
    def __repr__(self):
        return f"<UserInteraction(user_id={self.user_id}, product_id={self.product_id})>"


class UserReview(Base):
    """用户评价表"""
    __tablename__ = 'user_reviews'
    
    review_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    product_id = Column(Integer, nullable=False, index=True)
    rating = Column(Float, nullable=False)  # 0-5分评分
    review_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关系
    user = relationship("User", back_populates="reviews")
    
    # 索引
    __table_args__ = (
        Index('idx_user_review', 'user_id'),
        Index('idx_product_review', 'product_id'),
    )
    
    def __repr__(self):
        return f"<UserReview(user_id={self.user_id}, product_id={self.product_id}, rating={self.rating})>"


class GameMetadata(Base):
    """游戏元数据表"""
    __tablename__ = 'game_metadata'
    
    product_id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    app_name = Column(String(255))
    genres = Column(Text)  # JSON字符串存储
    tags = Column(Text)    # JSON字符串存储
    developer = Column(String(255))
    publisher = Column(String(255))
    metascore = Column(Integer)
    sentiment = Column(String(50))
    release_date = Column(String(20))
    price = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_title', 'title'),
        Index('idx_developer', 'developer'),
        Index('idx_release_date', 'release_date'),
    )
    
    def __repr__(self):
        return f"<GameMetadata(id={self.product_id}, title='{self.title}')>"


class RecommendationLog(Base):
    """推荐日志表"""
    __tablename__ = 'recommendation_logs'
    
    log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    recommended_items = Column(Text, nullable=False)  # JSON字符串存储推荐结果
    algorithm = Column(String(50), nullable=False)    # 使用的算法
    recall_time_ms = Column(Float)                    # 召回耗时(毫秒)
    ranking_time_ms = Column(Float)                   # 排序耗时(毫秒)
    total_time_ms = Column(Float)                     # 总耗时(毫秒)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_user_log', 'user_id'),
        Index('idx_algorithm', 'algorithm'),
        Index('idx_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<RecommendationLog(user_id={self.user_id}, algorithm='{self.algorithm}')>"


class UserFeedback(Base):
    """用户反馈表"""
    __tablename__ = 'user_feedback'
    
    feedback_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    feedback_type = Column(String(20), nullable=False)  # 'like', 'dislike', 'not_interested'
    recommendation_id = Column(String(50))  # 推荐批次ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_user_feedback', 'user_id'),
        Index('idx_product_feedback', 'product_id'),
        Index('idx_feedback_type', 'feedback_type'),
    )
    
    def __repr__(self):
        return f"<UserFeedback(user_id={self.user_id}, product_id={self.product_id}, type='{self.feedback_type}')>"


class UserLibrary(Base):
    """用户游戏库表"""
    __tablename__ = 'user_library'
    
    library_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    product_id = Column(Integer, nullable=False, index=True)
    app_id = Column(String(50), nullable=False)  # Steam App ID
    
    # 收藏和安装状态
    is_favorite = Column(Boolean, default=False, index=True)
    is_installed = Column(Boolean, default=False)
    
    # 购买信息
    purchase_date = Column(Date)
    purchase_price = Column(Numeric(10, 2))
    
    # 游玩数据
    playtime_hours = Column(Numeric(10, 2), default=0.0)
    last_played_at = Column(DateTime(timezone=True))
    
    # 成就数据
    achievement_progress = Column(Integer, default=0)  # 成就完成百分比
    achievements_unlocked = Column(Integer, default=0)
    achievements_total = Column(Integer, default=0)
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引和约束
    __table_args__ = (
        Index('idx_user_library', 'user_id'),
        Index('idx_user_favorite', 'user_id', 'is_favorite'),
        Index('idx_last_played', 'user_id', 'last_played_at'),
        Index('idx_user_product', 'user_id', 'product_id', unique=True),
    )
    
    def __repr__(self):
        return f"<UserLibrary(user_id={self.user_id}, product_id={self.product_id}, favorite={self.is_favorite})>"


class UserProfile(Base):
    """用户画像扩展表"""
    __tablename__ = 'user_profiles'
    
    profile_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, unique=True, index=True)
    
    # 基础信息
    avatar_url = Column(String(500))
    level = Column(Integer, default=1)
    exp = Column(Integer, default=0)
    exp_to_next_level = Column(Integer, default=1000)
    member_since = Column(Date)
    
    # Gamer DNA (JSON存储)
    gamer_dna_stats = Column(Text)  # JSON字符串
    primary_type = Column(String(50))
    secondary_type = Column(String(50))
    
    # Bento Stats
    total_playtime_hours = Column(Numeric(10, 2), default=0.0)
    games_owned = Column(Integer, default=0)
    library_value = Column(Numeric(10, 2), default=0.0)
    achievements_unlocked = Column(Integer, default=0)
    perfect_games = Column(Integer, default=0)
    avg_session_minutes = Column(Integer, default=0)
    
    # Favorite Genres (JSON存储)
    favorite_genres = Column(Text)  # JSON字符串
    
    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # 索引
    __table_args__ = (
        Index('idx_user_profile', 'user_id'),
    )
    
    def __repr__(self):
        return f"<UserProfile(user_id={self.user_id}, level={self.level})>"
