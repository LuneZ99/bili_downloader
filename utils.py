#!/usr/bin/env python3
"""
工具函数模块

提供项目公共的工具函数：
- 统一日志配置
- 跨平台编码处理
"""

import asyncio
import logging
import sys
import traceback
from functools import wraps
from typing import Optional

from bilibili_api.exceptions import ResponseCodeException, NetworkException


def api_retry_decorator(max_retries=5, initial_wait_time=3):
    """
    Bilibili API 请求重试装饰器

    Args:
        max_retries: 最大重试次数
        initial_wait_time: 初始等待时间（秒）
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            retries = max_retries
            current_wait_time = initial_wait_time

            while retries > 0:
                try:
                    return await func(self, *args, **kwargs)
                except (ResponseCodeException, NetworkException) as e:
                    if "-352" in str(e):
                        self.logger.warning("Credential expired (-352). Refreshing...")
                        if hasattr(self, 'credential') and self.credential and hasattr(self.credential, 'ac_time_value'):
                            try:
                                await self.credential.refresh()
                                self.logger.info("Credential refreshed successfully. Retrying request...")
                                continue  # 立即重试
                            except Exception as refresh_error:
                                self.logger.error(f"Failed to refresh credential: {refresh_error}")
                                self.logger.error(traceback.format_exc())
                                break  # 刷新失败，中断重试
                        else:
                            self.logger.error("Credential expired (-352), but cannot refresh without 'ac_time_value'. Please update your credentials.")
                            break
                    elif "412" in str(e):
                        self.logger.warning(f"Request rate-limited (412). Retrying in {current_wait_time} seconds... ({retries-1} retries left)")
                        await asyncio.sleep(current_wait_time)
                        current_wait_time *= 2  # 指数退避
                        retries -= 1
                    else:
                        self.logger.error(f"An unexpected API error occurred: {e}")
                        self.logger.error(traceback.format_exc())
                        break  # 其他错误，中断重试
                except Exception as e:
                    self.logger.error(f"An unexpected error occurred in decorated function: {e}")
                    self.logger.error(traceback.format_exc())
                    break  # 未知错误，中断重试
            
            # 如果所有重试都失败了
            self.logger.error(f"Function {func.__name__} failed after {max_retries} retries.")
            return None
        return wrapper
    return decorator


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