#!/usr/bin/env python3
"""
工具函数模块

提供项目公共的工具函数：
- 统一日志配置
- 跨平台编码处理
"""

import logging
import sys
from typing import Optional


def setup_logging(log_file: str = 'logs.txt', logger_name: Optional[str] = None) -> logging.Logger:
    """
    设置统一的日志配置，解决跨平台编码问题
    
    Args:
        log_file: 日志文件名（默认: logs.txt）
        logger_name: 日志记录器名称（可选）
        
    Returns:
        配置好的 Logger 对象
    """
    # 创建或获取logger
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    
    # 避免重复配置
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # 设置日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        # 创建文件处理器（明确指定UTF-8编码）
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"⚠️  创建文件日志处理器失败: {e}")
    
    # 创建控制台处理器
    try:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        
        # 在Windows下设置控制台编码
        if hasattr(console_handler.stream, 'reconfigure'):
            try:
                console_handler.stream.reconfigure(encoding='utf-8')
            except Exception:
                pass  # 忽略重配置失败
        
        logger.addHandler(console_handler)
    except Exception as e:
        print(f"⚠️  创建控制台日志处理器失败: {e}")
    
    return logger


def get_logger(name: str, log_file: str = 'logs.txt') -> logging.Logger:
    """
    获取指定名称的logger，自动配置编码
    
    Args:
        name: logger名称
        log_file: 日志文件名
        
    Returns:
        配置好的 Logger 对象
    """
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    # 使用统一配置
    setup_logging(log_file, name)
    return logger


def ensure_utf8_encoding():
    """
    确保系统编码支持UTF-8（主要用于Windows系统）
    """
    try:
        # 尝试设置默认编码（仅在某些Python版本中有效）
        if hasattr(sys, 'setdefaultencoding'):
            sys.setdefaultencoding('utf-8')
    except Exception:
        pass  # 忽略设置失败
    
    # 检查并警告编码问题
    try:
        test_str = "🔑测试中文编码✅"
        test_str.encode(sys.getdefaultencoding())
    except UnicodeEncodeError:
        print("⚠️  系统默认编码不支持中文和emoji，可能出现显示问题")
        print("💡 建议在Windows下使用 `chcp 65001` 命令切换到UTF-8编码")