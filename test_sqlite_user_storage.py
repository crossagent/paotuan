#!/usr/bin/env python
"""
SQLite用户存储测试脚本

使用方法：
    python test_sqlite_user_storage.py

此脚本会：
1. 创建一个测试用户
2. 更新用户信息
3. 验证更改是否立即生效
4. 清理测试数据
"""

import os
import sys
import logging
import uuid
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from persistence.user_repository import UserRepository
from web.auth import pwd_context

def main():
    """执行测试过程"""
    logger.info("开始SQLite用户存储测试...")
    
    # 创建用户仓库
    db_path = "web/data/users.db"
    user_repository = UserRepository(db_path)
    
    # 生成测试用户数据
    test_username = f"test_user_{uuid.uuid4().hex[:8]}"
    test_email = f"{test_username}@example.com"
    test_password = "test_password"
    hashed_password = pwd_context.hash(test_password)
    
    try:
        # 步骤1: 创建测试用户
        logger.info(f"创建测试用户: {test_username}")
        user_data = {
            "username": test_username,
            "email": test_email,
            "hashed_password": hashed_password
        }
        
        created_user = user_repository.create_user(user_data)
        user_id = created_user["id"]
        logger.info(f"用户创建成功，ID: {user_id}")
        
        # 步骤2: 更新用户信息
        new_email = f"updated_{test_username}@example.com"
        logger.info(f"更新用户邮箱: {new_email}")
        
        update_data = {
            "email": new_email
        }
        
        updated_user = user_repository.update_user(user_id, update_data)
        logger.info(f"用户更新成功: {updated_user}")
        
        # 步骤3: 验证更改是否立即生效
        retrieved_user = user_repository.get_user_by_id(user_id)
        
        if retrieved_user["email"] == new_email:
            logger.info("验证成功: 用户更改立即生效")
        else:
            logger.error(f"验证失败: 用户邮箱未更新，期望 {new_email}，实际 {retrieved_user['email']}")
            return False
        
        # 步骤4: 清理测试数据
        logger.info(f"清理测试用户: {test_username}")
        user_repository.delete_user(user_id)
        
        # 验证用户已删除
        deleted_user = user_repository.get_user_by_id(user_id)
        if deleted_user is None:
            logger.info("测试用户已成功删除")
        else:
            logger.error("测试用户删除失败")
            return False
        
        logger.info("SQLite用户存储测试完成，所有测试通过")
        return True
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
