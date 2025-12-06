"""
统一日志配置模块
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime

from backend.config import settings


class ColoredFormatter(logging.Formatter):
    """带颜色的日志格式化器（用于控制台输出）"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器（用于文件输出）"""
    
    def format(self, record):
        # 构建结构化日志
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'ip'):
            log_data['ip'] = record.ip
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'algorithm'):
            log_data['algorithm'] = record.algorithm
        
        # 格式化输出（简单JSON格式，实际可以使用json.dumps）
        parts = [f"{k}={v}" for k, v in log_data.items()]
        return " | ".join(parts)


def setup_logging(
    log_dir: Optional[str] = None,
    log_level: Optional[str] = None,
    enable_file_logging: bool = True,
    enable_console_logging: bool = True
) -> None:
    """
    设置日志系统
    
    Args:
        log_dir: 日志目录路径，默认为项目根目录下的 logs 目录
        log_level: 日志级别，默认从配置读取
        enable_file_logging: 是否启用文件日志
        enable_console_logging: 是否启用控制台日志
    """
    # 确定日志级别
    level = log_level or settings.LOG_LEVEL
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 创建日志目录
    if log_dir is None:
        log_dir = Path(__file__).parent.parent / "logs"
    else:
        log_dir = Path(log_dir)
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # 清除现有的处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    if enable_console_logging:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        
        if settings.DEBUG:
            # 开发环境使用彩色格式
            console_formatter = ColoredFormatter(
                '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        else:
            # 生产环境使用简洁格式
            console_formatter = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # 文件处理器
    if enable_file_logging:
        # 访问日志
        access_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_dir / "access.log"),
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10,
            encoding='utf-8'
        )
        access_handler.setLevel(logging.INFO)
        access_handler.addFilter(lambda record: record.name.startswith('backend.api'))
        access_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(access_handler)
        
        # 业务日志
        business_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_dir / "business.log"),
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10,
            encoding='utf-8'
        )
        business_handler.setLevel(logging.INFO)
        business_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(business_handler)
        
        # 错误日志
        error_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_dir / "error.log"),
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=20,  # 错误日志保留更多
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)
        
        # 性能日志
        performance_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_dir / "performance.log"),
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=10,
            encoding='utf-8'
        )
        performance_handler.setLevel(logging.INFO)
        performance_handler.addFilter(lambda record: hasattr(record, 'duration_ms'))
        performance_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(performance_handler)
        
        # 审计日志（安全相关操作）
        audit_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_dir / "audit.log"),
            maxBytes=100 * 1024 * 1024,  # 100MB
            backupCount=30,  # 审计日志保留更久
            encoding='utf-8'
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.addFilter(lambda record: record.name.startswith('backend.auth'))
        audit_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(audit_handler)
    
    # 设置第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aioredis").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
        
    Returns:
        日志记录器实例
    """
    return logging.getLogger(name)


def mask_sensitive_data(data: dict) -> dict:
    """
    脱敏敏感数据
    
    Args:
        data: 原始数据字典
        
    Returns:
        脱敏后的数据字典
    """
    sensitive_keys = ['password', 'password_hash', 'token', 'access_token', 'refresh_token', 'secret']
    masked_data = data.copy()
    
    for key in sensitive_keys:
        if key in masked_data:
            value = str(masked_data[key])
            if len(value) > 8:
                masked_data[key] = value[:4] + "****" + value[-4:]
            else:
                masked_data[key] = "****"
    
    # 邮箱脱敏
    if 'email' in masked_data:
        email = str(masked_data['email'])
        if '@' in email:
            parts = email.split('@')
            if len(parts[0]) > 2:
                masked_data['email'] = parts[0][:2] + "***@" + parts[1]
            else:
                masked_data['email'] = "***@" + parts[1]
    
    return masked_data

