# FilmSense API 文档

## 概述

FilmSense 是一个 Steam 游戏推荐系统的后端 API 服务，基于 FastAPI 构建。

- **基础URL**: `http://localhost:8000`
- **API版本前缀**: `/api/v1`
- **文档地址**: `/docs` (Swagger UI) 或 `/redoc` (ReDoc)

## 通用响应格式

大部分接口返回统一的 JSON 格式：

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

## 认证方式

使用 JWT Bearer Token 认证。在需要认证的接口中，请在请求头中添加：

```
Authorization: Bearer <access_token>
```

---

## 目录

1. [健康检查](#健康检查)
2. [认证模块 (Authentication)](#认证模块)
3. [用户模块 (Users)](#用户模块)
4. [游戏库模块 (Library)](#游戏库模块)
5. [游戏模块 (Games)](#游戏模块)
6. [推荐模块 (Recommendations)](#推荐模块)
7. [交互模块 (Interactions)](#交互模块)

---

## 健康检查

### GET /health

健康检查接口，用于监控服务状态。

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": 1702123456.789,
  "version": "1.0.0"
}
```

### GET /

根路径，返回欢迎信息。

**响应示例**:
```json
{
  "message": "Welcome to FilmSense API",
  "docs": "/docs",
  "version": "1.0.0"
}
```

---

## 认证模块

### POST /api/v1/auth/register

用户注册。

**请求体**:
```json
{
  "username": "string",    // 3-50字符，仅支持字母、数字、下划线、连字符
  "email": "user@example.com",
  "password": "string"     // 8-128字符
}
```

**响应** (201 Created):
```json
{
  "user_id": 1,
  "username": "testuser",
  "email": "user@example.com",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

**错误码**:
- `400`: 用户名或邮箱已存在
- `422`: 参数验证失败

---

### POST /api/v1/auth/login

用户登录，获取访问令牌。

**请求体**:
```json
{
  "username": "string",
  "password": "string"
}
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**错误码**:
- `401`: 用户名或密码错误

---

### POST /api/v1/auth/refresh

刷新访问令牌。

**请求体**:
```json
{
  "refresh_token": "string"
}
```

**响应**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**错误码**:
- `401`: 无效的刷新令牌

---

### POST /api/v1/auth/logout

用户登出。

**认证**: 需要 Bearer Token

**响应**:
```json
{
  "message": "Logout successful. Please remove tokens from client storage."
}
```

---

### GET /api/v1/auth/verify

验证令牌有效性。

**认证**: 需要 Bearer Token

**响应**:
```json
{
  "valid": true,
  "user_id": 1,
  "username": "testuser"
}
```

**错误码**:
- `401`: 令牌无效或过期
- `404`: 用户不存在

---

## 用户模块

### GET /api/v1/user/profile

获取当前用户资料。

**认证**: 需要 Bearer Token

**响应**:
```json
{
  "user_id": 1,
  "username": "testuser",
  "email": "user@example.com",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T00:00:00"
}
```

---

### PUT /api/v1/user/profile

更新用户资料。

**认证**: 需要 Bearer Token

**请求体**:
```json
{
  "username": "newusername",  // 可选
  "email": "newemail@example.com"  // 可选
}
```

**响应**:
```json
{
  "user_id": 1,
  "username": "newusername",
  "email": "newemail@example.com",
  "created_at": "2024-01-01T00:00:00",
  "updated_at": "2024-01-01T12:00:00"
}
```

---

### GET /api/v1/user/profile/complete

获取完整的用户画像（包含 Gamer DNA 和 Bento Stats）。

**查询参数**:
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| user_id | string | 是 | 用户ID |

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "user_id": "1",
    "username": "testuser",
    "avatar_url": null,
    "level": 5,
    "exp": 2500,
    "exp_to_next_level": 1000,
    "member_since": "2024-01-01",
    "gamer_dna": {
      "description": "你的游戏基因分析",
      "stats": [
        {"name": "探索", "value": 80, "max": 100},
        {"name": "策略", "value": 65, "max": 100}
      ],
      "primary_type": "探索者",
      "secondary_type": "策略家"
    },
    "bento_stats": {
      "total_playtime_hours": 1250.5,
      "games_owned": 150,
      "library_value": 2500.00,
      "achievements_unlocked": 500,
      "perfect_games": 10,
      "avg_session_minutes": 90
    },
    "favorite_genres": ["RPG", "Action", "Adventure"],
    "recent_activity": {
      "last_played_game_id": "730",
      "last_played_at": "2024-01-15T18:30:00"
    }
  }
}
```

---

### GET /api/v1/user/interactions

获取用户交互历史。

**认证**: 需要 Bearer Token

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| limit | int | 50 | 限制数量 |
| offset | int | 0 | 偏移量 |

**响应**:
```json
{
  "interactions": [
    {
      "interaction_id": 1,
      "product_id": 730,
      "timestamp": 1702123456,
      "play_hours": 25.5,
      "early_access": false,
      "created_at": "2024-01-01T00:00:00"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

---

### GET /api/v1/user/played-games

获取用户已玩游戏列表。

**认证**: 需要 Bearer Token

**响应**:
```json
{
  "user_id": 1,
  "played_games": [730, 570, 440],
  "total": 3
}
```

---

### GET /api/v1/user/preferences

获取用户偏好分析。

**认证**: 需要 Bearer Token

**响应**:
```json
{
  "user_id": 1,
  "preferences": {
    "favorite_genres": ["Action", "Adventure", "RPG"],
    "favorite_developers": ["FromSoftware", "CD Projekt"],
    "avg_play_hours": 25.5,
    "total_games": 50,
    "recent_activity": [730, 570, 440, 292030, 1245620]
  }
}
```

---

### DELETE /api/v1/user/account

删除用户账户。

**认证**: 需要 Bearer Token

**⚠️ 危险操作**: 将永久删除用户账户和所有相关数据。

**响应**:
```json
{
  "message": "Account deletion initiated. All user data will be removed.",
  "user_id": 1
}
```

---

## 游戏库模块

### GET /api/v1/user/library

获取用户游戏库。

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| user_id | string | 必填 | 用户ID |
| filter | string | "all" | 筛选类型: all/installed/favorites/recent |
| sort_by | string | "recent" | 排序方式: recent/name/playtime |
| page | int | 1 | 页码 |
| limit | int | 50 | 每页数量 (1-100) |

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "games": [
      {
        "app_id": "730",
        "app_name": "Counter-Strike 2",
        "genres": ["Action", "FPS"],
        "tags": ["Multiplayer", "Competitive"],
        "playtime_hours": 1250.5,
        "last_played_at": "2024-01-15T18:30:00",
        "last_played_relative": "2小时前",
        "is_installed": true,
        "is_favorite": true,
        "achievement_progress": 75,
        "achievements_unlocked": 150,
        "achievements_total": 200,
        "purchase_date": "2020-01-01",
        "purchase_price": 0.0
      }
    ],
    "summary": {
      "total_games": 150,
      "installed_count": 25,
      "favorites_count": 10
    },
    "pagination": {
      "page": 1,
      "limit": 50,
      "total": 150,
      "has_more": true
    }
  }
}
```

---

### POST /api/v1/user/library/toggle-favorite

切换游戏收藏状态。

**请求体**:
```json
{
  "user_id": "1",
  "game_id": "730"
}
```

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "success": true,
    "is_liked": true,
    "message": "已添加到收藏"
  }
}
```

---

### GET /api/v1/user/favorites

获取用户收藏的游戏ID列表。

**查询参数**:
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| user_id | string | 是 | 用户ID |

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "games": ["730", "570", "440"]
  }
}
```

---

## 游戏模块

### GET /api/v1/games

获取游戏列表（发现页）。

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| limit | int | 20 | 每页数量 (1-50) |
| genre | string | null | 按品类筛选 (如: RPG, Action) |
| tags | string | null | 按标签筛选（逗号分隔） |
| search | string | null | 搜索关键词 |
| sort_by | string | "popular" | 排序方式: popular/newest/price_asc/price_desc/rating |
| price_min | float | null | 最低价格 |
| price_max | float | null | 最高价格 |

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "games": [
      {
        "app_id": "730",
        "app_name": "Counter-Strike 2",
        "genres": ["Action", "FPS"],
        "tags": ["Multiplayer", "Competitive"],
        "price": 0.0,
        "discount_price": null,
        "developer": "Valve",
        "publisher": "Valve",
        "release_date": "2023-09-27",
        "specs": ["Multi-player", "Steam Achievements"],
        "early_access": false
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 1000,
      "total_pages": 50,
      "has_more": true
    },
    "filters_applied": {
      "genre": null,
      "tags": null,
      "search": null,
      "sort_by": "popular",
      "price_min": null,
      "price_max": null
    }
  }
}
```

---

### GET /api/v1/games/{app_id}

获取单个游戏的详情信息。

**路径参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| app_id | string | Steam App ID |

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "app_id": "730",
    "app_name": "Counter-Strike 2",
    "description": "详细游戏描述...",
    "short_description": "简短描述...",
    "genres": ["Action", "FPS"],
    "tags": ["Multiplayer", "Competitive", "Shooter"],
    "developer": "Valve",
    "publisher": "Valve",
    "release_date": "2023-09-27",
    "price": 0.0,
    "discount_price": null,
    "discount_percent": 0,
    "specs": ["Multi-player", "Steam Achievements", "Full controller support"],
    "languages": ["English", "Chinese", "Japanese"],
    "store_url": "https://store.steampowered.com/app/730",
    "reviews_url": "https://store.steampowered.com/app/730#reviews",
    "early_access": false
  }
}
```

**错误码**:
- `404`: 游戏不存在

---

### GET /api/v1/games/genres

获取所有可用的游戏品类列表。

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "genres": [
      {"id": "action", "name": "Action", "count": 5000},
      {"id": "rpg", "name": "RPG", "count": 3000},
      {"id": "adventure", "name": "Adventure", "count": 2500}
    ]
  }
}
```

---

### GET /api/v1/games/tags

获取所有可用的游戏标签列表（前50个最热门）。

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "tags": [
      {"id": "multiplayer", "name": "Multiplayer", "count": 8000},
      {"id": "singleplayer", "name": "Singleplayer", "count": 7500},
      {"id": "indie", "name": "Indie", "count": 6000}
    ]
  }
}
```

---

## 推荐模块

### GET /api/v1/recommendations

获取个性化推荐。

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| user_id | int | 必填 | 目标用户ID |
| topk | int | 10 | 推荐数量 (1-100) |
| algorithm | string | "auto" | 推荐算法: auto/embedding/popularity/content |
| ranking_strategy | string | "default" | 排序策略: default/diversity_focused/quality_focused |
| diversity_strength | float | null | 多样性强度 (0.0-1.0) |

**支持的算法**:
- `auto`: 自动选择最适合的算法
- `embedding`: 基于用户嵌入的协同过滤
- `popularity`: 基于流行度的推荐
- `content`: 基于内容的推荐

**支持的排序策略**:
- `default`: 默认平衡策略
- `diversity_focused`: 多样性优先策略
- `quality_focused`: 质量优先策略

**响应**:
```json
{
  "user_id": 1,
  "recommendations": [
    {
      "product_id": 730,
      "title": "Counter-Strike 2",
      "app_name": "Counter-Strike 2",
      "genres": ["Action", "FPS"],
      "tags": ["Multiplayer", "Competitive"],
      "developer": "Valve",
      "publisher": "Valve",
      "metascore": 90,
      "sentiment": "Very Positive",
      "release_date": "2023-09-27",
      "price": 0.0,
      "discount_price": null,
      "description": "游戏描述...",
      "short_description": "简短描述...",
      "specs": ["Multi-player"],
      "url": "https://store.steampowered.com/app/730",
      "reviews_url": "https://store.steampowered.com/app/730#reviews",
      "early_access": false,
      "score": 0.95
    }
  ],
  "algorithm": "embedding",
  "timestamp": 1702123456,
  "total_time_ms": 125.5,
  "recall_time_ms": 50.2,
  "ranking_time_ms": 75.3
}
```

**错误码**:
- `400`: 参数验证失败
- `404`: 用户不存在

---

### GET /api/v1/recommendations/explanation

获取推荐解释。

**查询参数**:
| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| user_id | int | 是 | 用户ID |
| product_id | int | 是 | 游戏ID |

**响应**:
```json
{
  "product_id": 730,
  "explanation": "基于您最近游玩的游戏历史进行推荐",
  "influential_games": [
    {"product_id": 570, "title": "Dota 2", "weight": 0.8},
    {"product_id": 440, "title": "Team Fortress 2", "weight": 0.6}
  ],
  "algorithm": "embedding"
}
```

---

### GET /api/v1/recommendations/popular

获取热门游戏列表。

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| limit | int | 20 | 返回数量 (1-100) |
| genre | string | null | 游戏类型过滤 |

**响应**:
```json
{
  "games": [
    {"product_id": 730, "score": 0.98},
    {"product_id": 570, "score": 0.95}
  ],
  "genre": null,
  "total": 20,
  "timestamp": 1702123456
}
```

---

### GET /api/v1/recommendations/trending

获取趋势游戏列表。

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| limit | int | 20 | 返回数量 (1-100) |
| time_window | string | "week" | 时间窗口: week/month |

**响应**:
```json
{
  "games": [
    {"product_id": 730, "score": 0.98},
    {"product_id": 570, "score": 0.95}
  ],
  "time_window": "week",
  "total": 20,
  "timestamp": 1702123456
}
```

---

### GET /api/v1/recommendations/similar/{item_id}

获取相似游戏推荐。

**路径参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| item_id | int | 目标游戏ID |

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| limit | int | 10 | 返回数量 (1-50) |

**响应**:
```json
{
  "target_item_id": 730,
  "similar_games": [
    {"product_id": 570, "similarity": 0.92},
    {"product_id": 440, "similarity": 0.88}
  ],
  "total": 10,
  "timestamp": 1702123456
}
```

---

### GET /api/v1/recommendations/stats

获取推荐系统统计信息。

**认证**: 需要 Bearer Token

**响应**:
```json
{
  "cache_stats": {
    "keyspace_hits": 10000,
    "keyspace_misses": 500
  },
  "cache_hit_rate": 95.24,
  "total_cache_requests": 10500,
  "timestamp": 1702123456
}
```

---

## 交互模块

### POST /api/v1/interactions/interact

记录用户交互事件。

**请求体**:
```json
{
  "user_id": 1,
  "product_id": 730,
  "timestamp": 1702123456,  // 可选，默认当前时间
  "play_hours": 2.5,        // 可选
  "early_access": false     // 可选
}
```

**响应**:
```json
{
  "status": "success",
  "message": "Interaction recorded successfully",
  "interaction_id": 12345
}
```

> **注意**: 此接口也可通过 `POST /api/v1/interact` 访问（兼容别名）。

---

### POST /api/v1/interactions/review

创建用户评价。

**认证**: 需要 Bearer Token

**请求体**:
```json
{
  "user_id": 1,
  "product_id": 730,
  "rating": 4.5,           // 0-5
  "review_text": "很棒的游戏！"  // 可选
}
```

**响应**:
```json
{
  "review_id": 1,
  "user_id": 1,
  "product_id": 730,
  "rating": 4.5,
  "review_text": "很棒的游戏！",
  "created_at": "2024-01-01T00:00:00"
}
```

**错误码**:
- `400`: 该游戏已有评价
- `403`: 只能为自己创建评价

---

### GET /api/v1/interactions/review/{product_id}

获取用户对特定游戏的评价。

**认证**: 需要 Bearer Token

**路径参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| product_id | int | 游戏ID |

**响应**:
```json
{
  "review_id": 1,
  "user_id": 1,
  "product_id": 730,
  "rating": 4.5,
  "review_text": "很棒的游戏！",
  "created_at": "2024-01-01T00:00:00"
}
```

**错误码**:
- `404`: 评价不存在

---

### POST /api/v1/interactions/feedback

记录用户反馈。

**认证**: 需要 Bearer Token

**请求体**:
```json
{
  "user_id": 1,
  "product_id": 730,
  "feedback_type": "like",        // like/dislike/not_interested
  "recommendation_id": "abc123"   // 可选，推荐批次ID
}
```

**响应**:
```json
{
  "status": "success",
  "message": "Feedback recorded successfully",
  "feedback_type": "like"
}
```

**错误码**:
- `403`: 只能为自己创建反馈

---

### GET /api/v1/interactions/history

获取用户最近的交互历史。

**认证**: 需要 Bearer Token

**查询参数**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| limit | int | 20 | 限制数量 |

**响应**:
```json
{
  "user_id": 1,
  "history": [
    {
      "product_id": 730,
      "position": 1,
      "title": "Counter-Strike 2",
      "interaction_type": "play"
    }
  ],
  "total": 1
}
```

---

### DELETE /api/v1/interactions/history

清除用户交互历史。

**认证**: 需要 Bearer Token

**⚠️ 危险操作**: 将清除用户的推荐历史数据。

**响应**:
```json
{
  "status": "success",
  "message": "Interaction history cleared successfully",
  "user_id": 1
}
```

---

### GET /api/v1/interactions/stats

获取用户交互统计信息。

**认证**: 需要 Bearer Token

**响应**:
```json
{
  "user_id": 1,
  "total_interactions": 150,
  "recent_games": [730, 570, 440, 292030, 1245620],
  "recent_activity_count": 5,
  "user_level": "active"  // cold/new/active
}
```

---

## 错误响应格式

所有错误响应遵循以下格式：

```json
{
  "detail": "错误描述信息"
}
```

或带有请求ID的格式：

```json
{
  "error": "Internal server error",
  "message": "An unexpected error occurred",
  "request_id": "abc12345"
}
```

### 常见HTTP状态码

| 状态码 | 描述 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未认证或令牌无效 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 422 | 参数验证失败 |
| 500 | 服务器内部错误 |

---

## 数据模型

### User (用户)

| 字段 | 类型 | 描述 |
|------|------|------|
| user_id | int | 用户ID |
| username | string | 用户名 (3-50字符) |
| email | string | 邮箱地址 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### GameInfo (游戏信息)

| 字段 | 类型 | 描述 |
|------|------|------|
| product_id | int | 游戏ID |
| title | string | 游戏标题 |
| app_name | string | Steam应用名称 |
| genres | string[] | 游戏品类 |
| tags | string[] | 游戏标签 |
| developer | string | 开发商 |
| publisher | string | 发行商 |
| metascore | int | Metacritic评分 |
| sentiment | string | 用户评价情感 |
| release_date | string | 发布日期 |
| price | float | 价格 |
| discount_price | float | 折扣价 |
| description | string | 详细描述 |
| short_description | string | 简短描述 |
| specs | string[] | 游戏特性 |
| url | string | 商店链接 |
| reviews_url | string | 评测链接 |
| early_access | bool | 是否抢先体验 |
| score | float | 推荐分数 |

### LibraryGame (游戏库游戏)

| 字段 | 类型 | 描述 |
|------|------|------|
| app_id | string | Steam App ID |
| app_name | string | 游戏名称 |
| genres | string[] | 游戏品类 |
| tags | string[] | 游戏标签 |
| playtime_hours | float | 游玩时长（小时） |
| last_played_at | string | 最后游玩时间 |
| last_played_relative | string | 相对时间描述 |
| is_installed | bool | 是否已安装 |
| is_favorite | bool | 是否收藏 |
| achievement_progress | int | 成就完成百分比 (0-100) |
| achievements_unlocked | int | 已解锁成就数 |
| achievements_total | int | 总成就数 |
| purchase_date | string | 购买日期 |
| purchase_price | float | 购买价格 |

### GamerDNA (玩家DNA)

| 字段 | 类型 | 描述 |
|------|------|------|
| description | string | 描述 |
| stats | GamerDNAStat[] | 6维属性数据 |
| primary_type | string | 主要类型 |
| secondary_type | string | 次要类型 |

### BentoStats (统计数据)

| 字段 | 类型 | 描述 |
|------|------|------|
| total_playtime_hours | float | 总游玩时长（小时） |
| games_owned | int | 拥有游戏数 |
| library_value | float | 游戏库总价值 |
| achievements_unlocked | int | 已解锁成就数 |
| perfect_games | int | 100%完成的游戏数 |
| avg_session_minutes | int | 平均游戏时长（分钟） |

---

## 配置说明

### 环境变量

| 变量名 | 默认值 | 描述 |
|--------|--------|------|
| API_V1_PREFIX | /api/v1 | API版本前缀 |
| DEBUG | false | 调试模式 |
| LOG_LEVEL | INFO | 日志级别 |
| DATABASE_URL | - | 数据库连接URL |
| DB_TYPE | postgresql | 数据库类型 (postgresql/mysql) |
| DB_HOST | localhost | 数据库主机 |
| DB_PORT | - | 数据库端口 |
| DB_NAME | filmsense | 数据库名称 |
| DB_USER | user | 数据库用户 |
| DB_PASSWORD | password | 数据库密码 |
| REDIS_URL | redis://localhost:6379 | Redis连接URL |
| JWT_SECRET_KEY | - | JWT密钥（生产环境必须修改） |
| JWT_ALGORITHM | HS256 | JWT算法 |
| JWT_EXPIRATION_HOURS | 24 | JWT过期时间（小时） |
| ALLOWED_ORIGINS | * | CORS允许的源 |

---

## 推荐算法说明

### 算法选择策略

系统根据用户交互次数自动选择最适合的推荐算法：

| 交互次数 | 选择算法 | 说明 |
|----------|----------|------|
| < 3 | popularity | 冷启动用户，使用热门推荐 |
| 3-5 | content | 少量交互，使用内容推荐 |
| > 5 | embedding | 足够交互，使用协同过滤 |

### 排序策略

- **default**: 平衡推荐质量和多样性
- **diversity_focused**: 优先保证推荐结果的多样性
- **quality_focused**: 优先保证推荐质量（相关性）

---

## 版本信息

- **当前版本**: 1.0.0
- **API前缀**: /api/v1
- **框架**: FastAPI
- **数据库**: PostgreSQL / MySQL
- **缓存**: Redis
- **向量索引**: FAISS
