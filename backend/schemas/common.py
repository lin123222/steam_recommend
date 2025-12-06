"""
通用的 Pydantic 模型
"""

from typing import Any, Optional, Generic, TypeVar
from pydantic import BaseModel, Field

DataT = TypeVar('DataT')


class ResponseModel(BaseModel, Generic[DataT]):
    """
    统一的 API 响应模型
    
    所有接口返回统一的 JSON 格式：
    {
        "code": 200,
        "message": "success",
        "data": { ... }
    }
    """
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": 200,
                "message": "success",
                "data": {}
            }
        }


class PaginationModel(BaseModel):
    """分页模型"""
    page: int = Field(..., ge=1, description="当前页码")
    limit: int = Field(..., ge=1, description="每页数量")
    total: int = Field(..., ge=0, description="总数")
    total_pages: int = Field(..., ge=0, description="总页数")
    has_more: bool = Field(..., description="是否有更多数据")
