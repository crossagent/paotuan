#!/usr/bin/env python
"""
用户数据迁移脚本：将JSON用户数据迁移到SQLite数据库

使用方法：
    python migrate_users_to_sqlite.py

此脚本会：
1. 从JSON文件加载现有用户数据
2. 创建SQLite数据库和用户表
3. 将用户数据导入到SQLite数据库
4. 验证迁移结果
"""

import os
import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from persistence.user_repository import UserRepository
from web.auth import User

def main():
    """执行迁移过程"""
    logger.info("开始用户数据迁移...")
    
    # 检查JSON文件是否存在
    json_path = "web/data/users.json"
    if not os.path.exists(json_path):
        logger.error(f"JSON文件不存在: {json_path}")
        return False
    
    # 创建用户仓库
    db_path = "web/data/users.db"
    user_repository = UserRepository(db_path)
    
    try:
        # 执行迁移
        user_repository.migrate_from_json(json_path)
        
        # 验证迁移结果
        users = user_repository.get_all_users()
        logger.info(f"迁移完成，共迁移 {len(users)} 个用户")
        
        # 显示迁移的用户
        for i, user in enumerate(users, 1):
            logger.info(f"用户 {i}: {user['username']} (ID: {user['id']})")
        
        logger.info(f"用户数据已成功迁移到SQLite数据库: {db_path}")
        return True
    except Exception as e:
        logger.error(f"迁移过程中发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
