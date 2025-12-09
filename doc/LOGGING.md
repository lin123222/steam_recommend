# 日志系统使用文档

## 概述

后端已集成完整的日志系统，支持多级别日志记录、文件轮转、结构化日志等功能。

## 日志配置

### 环境变量

在 `.env` 文件中可以配置以下日志相关参数：

```env
# 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# 日志目录（可选，默认为项目根目录下的 logs/）
LOG_DIR=./logs

# 是否启用文件日志
ENABLE_FILE_LOGGING=true

# 是否启用控制台日志
ENABLE_CONSOLE_LOGGING=true

# 慢请求阈值（秒）
SLOW_REQUEST_THRESHOLD=1.0

# 慢查询阈值（秒）
SLOW_QUERY_THRESHOLD=0.5
```

## 日志文件

日志文件存储在 `logs/` 目录下，按类型分类：

- `access.log` - 访问日志（API请求）
- `business.log` - 业务日志（业务操作）
- `error.log` - 错误日志（ERROR级别及以上）
- `performance.log` - 性能日志（包含耗时信息的操作）
- `audit.log` - 审计日志（认证、授权等安全相关操作）

### 日志轮转

- 单文件最大：100MB
- 保留文件数：10个（error.log 和 audit.log 保留更多）
- 自动压缩：旧日志文件会自动压缩

## 使用方式

### 1. 基本日志记录

```python
from backend.logging_config import get_logger

logger = get_logger(__name__)

logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
logger.critical("严重错误")
```

### 2. 请求日志

请求日志由中间件自动记录，包含：
- HTTP方法、路径
- 状态码、响应时间
- 用户ID、IP地址
- 请求ID

### 3. 认证日志

使用 `log_auth_event` 记录认证相关操作：

```python
from backend.utils.logger import log_auth_event

log_auth_event(
    event_type="login",
    user_id=123,
    username="testuser",
    success=True,
    ip="192.168.1.1"
)
```

### 4. 推荐系统日志

使用 `log_recommendation` 记录推荐操作：

```python
from backend.utils.logger import log_recommendation

log_recommendation(
    user_id=123,
    algorithm="embedding",
    recommendations_count=10,
    total_time_ms=245.6,
    recall_time_ms=120.0,
    ranking_time_ms=125.6,
    from_cache=False
)
```

### 5. 缓存操作日志

使用 `log_cache_operation` 记录缓存操作：

```python
from backend.utils.logger import log_cache_operation

log_cache_operation(
    operation="GET",
    key="user:123:recommendations",
    hit=True,
    duration_ms=5.2,
    user_id=123
)
```

### 6. 数据库操作日志

使用 `log_database_operation` 记录数据库操作：

```python
from backend.utils.logger import log_database_operation

log_database_operation(
    operation="SELECT",
    table="users",
    duration_ms=45.2,
    success=True
)
```

### 7. 性能日志上下文管理器

使用 `log_performance` 记录代码块性能：

```python
from backend.utils.logger import log_performance

with log_performance("database_query", user_id=123):
    result = await db.query(...)
```

## 日志格式

### 控制台输出（开发环境）

```
2024-12-05 10:30:45 | INFO | backend.api.v1.endpoints.recommendations | Recommendation request completed
```

### 文件输出（结构化格式）

```
timestamp=2024-12-05T10:30:45.123Z | level=INFO | logger=backend.api.v1.endpoints.recommendations | message=Recommendation request completed | request_id=req_123456 | user_id=12345 | duration_ms=245.6
```

## 日志级别说明

- **DEBUG**: 详细的调试信息，通常只在开发时使用
- **INFO**: 一般信息，记录程序正常运行的关键操作
- **WARNING**: 警告信息，程序可以继续运行但需要注意
- **ERROR**: 错误信息，程序遇到错误但可以继续运行
- **CRITICAL**: 严重错误，可能导致程序崩溃

## 敏感信息处理

日志系统会自动脱敏以下敏感信息：
- 密码（password, password_hash）
- Token（access_token, refresh_token）
- 邮箱（部分脱敏）

## 最佳实践

1. **使用合适的日志级别**
   - 正常业务流程使用 INFO
   - 异常情况使用 WARNING 或 ERROR
   - 调试信息使用 DEBUG

2. **记录关键信息**
   - 用户操作（用户ID、IP）
   - 业务关键步骤
   - 错误详情（使用 exc_info=True）

3. **避免记录敏感信息**
   - 不要记录完整密码
   - 不要记录完整Token
   - 不要记录敏感业务数据

4. **性能考虑**
   - 高频操作使用 DEBUG 级别
   - 避免在循环中记录大量日志
   - 使用结构化日志便于后续分析

## 日志分析

### 查看错误日志

```bash
tail -f logs/error.log
```

### 查看访问日志

```bash
tail -f logs/access.log
```

### 搜索特定用户的操作

```bash
grep "user_id=123" logs/business.log
```

### 统计慢请求

```bash
grep "duration_ms" logs/performance.log | awk -F'duration_ms=' '{print $2}' | awk '{if($1>1000) print}'
```

## 故障排查

### 日志文件过大

检查日志级别设置，生产环境建议使用 INFO 或 WARNING。

### 日志未生成

1. 检查 `logs/` 目录是否存在且有写权限
2. 检查 `ENABLE_FILE_LOGGING` 配置
3. 检查日志级别设置

### 日志格式异常

确保使用 `get_logger(__name__)` 获取日志记录器，而不是直接使用 `logging.getLogger()`。

