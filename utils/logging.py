import logging
import sys
from typing import Optional

def setup_logger(level: str = 'INFO') -> logging.Logger:
    """设置日志记录器"""
    # 获取根日志记录器
    logger = logging.getLogger()
    
    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 添加控制台处理器
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter('%(asctime)s %(name)-8s %(levelname)-8s %(message)s [%(filename)s:%(lineno)d]')
    )
    logger.addHandler(handler)
    
    return logger
