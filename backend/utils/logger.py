"""
日志工具类
提供便捷的日志记录方法
"""

import logging
import time
import functools
from typing import Callable, Any, Optional
from contextlib import contextmanager

from backend.logging_config import get_logger


class LoggerMixin:
    """日志混入类，可以添加到任何类中"""
    
    @property
    def logger(self) -> logging.Logger:
        """获取日志记录器"""
        return get_logger(self.__class__.__module__)


def log_function_call(log_args: bool = False, log_result: bool = False, log_duration: bool = True):
    """
    函数调用日志装饰器
    
    Args:
        log_args: 是否记录函数参数
        log_result: 是否记录函数返回值
        log_duration: 是否记录执行时间
    """
    def decorator(func: Callable) -> Callable:
        logger = get_logger(func.__module__)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__name__}"
            
            try:
                if log_args:
                    # 脱敏敏感参数
                    safe_kwargs = {k: v for k, v in kwargs.items() if k not in ['password', 'password_hash']}
                    logger.debug(f"Calling {func_name} with args={args}, kwargs={safe_kwargs}")
                else:
                    logger.debug(f"Calling {func_name}")
                
                result = await func(*args, **kwargs)
                
                if log_duration:
                    duration = (time.time() - start_time) * 1000
                    logger.debug(f"{func_name} completed in {duration:.2f}ms")
                
                if log_result:
                    logger.debug(f"{func_name} returned: {result}")
                
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(
                    f"{func_name} failed after {duration:.2f}ms: {str(e)}",
                    exc_info=True
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            func_name = f"{func.__module__}.{func.__name__}"
            
            try:
                if log_args:
                    safe_kwargs = {k: v for k, v in kwargs.items() if k not in ['password', 'password_hash']}
                    logger.debug(f"Calling {func_name} with args={args}, kwargs={safe_kwargs}")
                else:
                    logger.debug(f"Calling {func_name}")
                
                result = func(*args, **kwargs)
                
                if log_duration:
                    duration = (time.time() - start_time) * 1000
                    logger.debug(f"{func_name} completed in {duration:.2f}ms")
                
                if log_result:
                    logger.debug(f"{func_name} returned: {result}")
                
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(
                    f"{func_name} failed after {duration:.2f}ms: {str(e)}",
                    exc_info=True
                )
                raise
        
        # 判断是否为异步函数
        if hasattr(func, '__code__') and 'async' in str(func.__code__.co_flags):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


@contextmanager
def log_performance(operation_name: str, logger: Optional[logging.Logger] = None, **extra_fields):
    """
    性能日志上下文管理器
    
    Usage:
        with log_performance("database_query", user_id=123):
            # 执行操作
            result = await db.query(...)
    """
    if logger is None:
        logger = get_logger(__name__)
    
    start_time = time.time()
    logger.info(f"Starting {operation_name}", extra=extra_fields)
    
    try:
        yield
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"{operation_name} failed after {duration:.2f}ms: {str(e)}",
            exc_info=True,
            extra={**extra_fields, 'duration_ms': duration}
        )
        raise
    else:
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"{operation_name} completed in {duration:.2f}ms",
            extra={**extra_fields, 'duration_ms': duration}
        )


def log_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[int] = None,
    ip: Optional[str] = None,
    request_id: Optional[str] = None,
    **kwargs
):
    """
    记录HTTP请求日志
    
    Args:
        method: HTTP方法
        path: 请求路径
        status_code: 响应状态码
        duration_ms: 请求耗时（毫秒）
        user_id: 用户ID
        ip: 客户端IP
        request_id: 请求ID
        **kwargs: 其他字段
    """
    logger = get_logger('backend.api.request')
    
    extra = {
        'method': method,
        'path': path,
        'status_code': status_code,
        'duration_ms': duration_ms,
        **kwargs
    }
    
    if user_id:
        extra['user_id'] = user_id
    if ip:
        extra['ip'] = ip
    if request_id:
        extra['request_id'] = request_id
    
    if status_code >= 500:
        logger.error(f"{method} {path} - {status_code} - {duration_ms:.2f}ms", extra=extra)
    elif status_code >= 400:
        logger.warning(f"{method} {path} - {status_code} - {duration_ms:.2f}ms", extra=extra)
    else:
        logger.info(f"{method} {path} - {status_code} - {duration_ms:.2f}ms", extra=extra)


def log_slow_request(
    method: str,
    path: str,
    duration_ms: float,
    threshold: float = 1000.0,
    **kwargs
):
    """
    记录慢请求日志
    
    Args:
        method: HTTP方法
        path: 请求路径
        duration_ms: 请求耗时（毫秒）
        threshold: 慢请求阈值（毫秒）
        **kwargs: 其他字段
    """
    if duration_ms > threshold:
        logger = get_logger('backend.api.slow_request')
        logger.warning(
            f"Slow request: {method} {path} took {duration_ms:.2f}ms (threshold: {threshold}ms)",
            extra={'method': method, 'path': path, 'duration_ms': duration_ms, **kwargs}
        )


def log_database_operation(
    operation: str,
    table: str,
    duration_ms: float,
    success: bool = True,
    error: Optional[str] = None,
    **kwargs
):
    """
    记录数据库操作日志
    
    Args:
        operation: 操作类型（SELECT, INSERT, UPDATE, DELETE等）
        table: 表名
        duration_ms: 操作耗时（毫秒）
        success: 是否成功
        error: 错误信息
        **kwargs: 其他字段
    """
    logger = get_logger('backend.database.operation')
    
    extra = {
        'operation': operation,
        'table': table,
        'duration_ms': duration_ms,
        'success': success,
        **kwargs
    }
    
    if success:
        logger.debug(f"DB {operation} on {table} - {duration_ms:.2f}ms", extra=extra)
    else:
        logger.error(f"DB {operation} on {table} failed: {error}", extra=extra)


def log_cache_operation(
    operation: str,
    key: str,
    hit: Optional[bool] = None,
    duration_ms: Optional[float] = None,
    **kwargs
):
    """
    记录缓存操作日志
    
    Args:
        operation: 操作类型（GET, SET, DELETE等）
        key: 缓存键
        hit: 是否命中（仅GET操作）
        duration_ms: 操作耗时（毫秒）
        **kwargs: 其他字段
    """
    logger = get_logger('backend.cache.operation')
    
    extra = {
        'operation': operation,
        'key': key,
        **kwargs
    }
    
    if hit is not None:
        extra['hit'] = hit
    if duration_ms is not None:
        extra['duration_ms'] = duration_ms
    
    if operation == 'GET' and hit is not None:
        status = "HIT" if hit else "MISS"
        logger.debug(f"Cache {operation} {key} - {status}", extra=extra)
    else:
        logger.debug(f"Cache {operation} {key}", extra=extra)


def log_recommendation(
    user_id: int,
    algorithm: str,
    recommendations_count: int,
    total_time_ms: float,
    recall_time_ms: Optional[float] = None,
    ranking_time_ms: Optional[float] = None,
    from_cache: bool = False,
    **kwargs
):
    """
    记录推荐系统日志
    
    Args:
        user_id: 用户ID
        algorithm: 使用的算法
        recommendations_count: 推荐结果数量
        total_time_ms: 总耗时（毫秒）
        recall_time_ms: 召回耗时（毫秒）
        ranking_time_ms: 排序耗时（毫秒）
        from_cache: 是否来自缓存
        **kwargs: 其他字段
    """
    logger = get_logger('backend.recommendation')
    
    extra = {
        'user_id': user_id,
        'algorithm': algorithm,
        'recommendations_count': recommendations_count,
        'total_time_ms': total_time_ms,
        'from_cache': from_cache,
        **kwargs
    }
    
    if recall_time_ms is not None:
        extra['recall_time_ms'] = recall_time_ms
    if ranking_time_ms is not None:
        extra['ranking_time_ms'] = ranking_time_ms
    
    cache_status = "cache" if from_cache else "compute"
    logger.info(
        f"Recommendation for user {user_id} using {algorithm} ({cache_status}): "
        f"{recommendations_count} items in {total_time_ms:.2f}ms",
        extra=extra
    )


def log_auth_event(
    event_type: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    success: bool = True,
    ip: Optional[str] = None,
    reason: Optional[str] = None,
    **kwargs
):
    """
    记录认证事件日志（审计日志）
    
    Args:
        event_type: 事件类型（register, login, logout, token_refresh等）
        user_id: 用户ID
        username: 用户名
        success: 是否成功
        ip: 客户端IP
        reason: 失败原因
        **kwargs: 其他字段
    """
    logger = get_logger('backend.auth.audit')
    
    extra = {
        'event_type': event_type,
        'success': success,
        **kwargs
    }
    
    if user_id:
        extra['user_id'] = user_id
    if username:
        extra['username'] = username
    if ip:
        extra['ip'] = ip
    if reason:
        extra['reason'] = reason
    
    status = "SUCCESS" if success else "FAILED"
    message = f"Auth {event_type} - {status}"
    if reason:
        message += f" - {reason}"
    
    if success:
        logger.info(message, extra=extra)
    else:
        logger.warning(message, extra=extra)

