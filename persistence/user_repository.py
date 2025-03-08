import sqlite3
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

class UserRepository:
    """用户数据仓库，使用SQLite存储用户数据"""
    
    def __init__(self, db_path: str = "web/data/users.db"):
        """
        初始化用户仓库
        
        Args:
            db_path (str): 数据库文件路径
        """
        self.db_path = db_path
        # 确保数据目录存在
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
        return conn
    
    def _init_db(self) -> None:
        """初始化数据库表结构"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # 创建用户表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                email TEXT,
                hashed_password TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL
            )
            ''')
            conn.commit()
            logger.info("数据库表结构初始化完成")
        except Exception as e:
            logger.error(f"初始化数据库失败: {str(e)}")
            raise
        finally:
            conn.close()
    
    def migrate_from_json(self, json_path: str = "web/data/users.json") -> None:
        """
        从JSON文件迁移用户数据到SQLite
        
        Args:
            json_path (str): JSON文件路径
        """
        if not os.path.exists(json_path):
            logger.warning(f"JSON文件不存在: {json_path}")
            return
        
        try:
            # 读取JSON数据
            with open(json_path, 'r', encoding='utf-8') as f:
                users_data = json.load(f)
            
            # 开始事务
            conn = self._get_connection()
            try:
                cursor = conn.cursor()
                
                # 检查是否已有用户数据
                cursor.execute("SELECT COUNT(*) FROM users")
                count = cursor.fetchone()[0]
                if count > 0:
                    logger.warning("数据库中已存在用户数据，跳过迁移")
                    return
                
                # 插入用户数据
                for user in users_data:
                    is_active = 1 if user.get('is_active', True) else 0
                    cursor.execute(
                        "INSERT INTO users (id, username, email, hashed_password, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            user['id'],
                            user['username'],
                            user.get('email', ''),
                            user['hashed_password'],
                            user.get('created_at', datetime.now().isoformat()),
                            is_active
                        )
                    )
                
                conn.commit()
                logger.info(f"成功从JSON迁移了 {len(users_data)} 个用户")
            except Exception as e:
                conn.rollback()
                logger.error(f"迁移数据失败: {str(e)}")
                raise
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"读取JSON文件失败: {str(e)}")
            raise
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """获取所有用户"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """通过ID获取用户"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """通过用户名获取用户"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建新用户
        
        Args:
            user_data (Dict[str, Any]): 用户数据，必须包含username, email, hashed_password
            
        Returns:
            Dict[str, Any]: 创建的用户数据
        """
        # 检查必要字段
        if 'username' not in user_data or 'hashed_password' not in user_data:
            raise ValueError("用户数据必须包含username和hashed_password")
        
        # 生成ID和创建时间
        user_id = user_data.get('id', str(uuid.uuid4()))
        created_at = user_data.get('created_at', datetime.now().isoformat())
        is_active = 1 if user_data.get('is_active', True) else 0
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 检查用户名是否已存在
            cursor.execute("SELECT id FROM users WHERE username = ?", (user_data['username'],))
            if cursor.fetchone():
                raise ValueError(f"用户名 '{user_data['username']}' 已存在")
            
            # 插入用户
            cursor.execute(
                "INSERT INTO users (id, username, email, hashed_password, created_at, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    user_data['username'],
                    user_data.get('email', ''),
                    user_data['hashed_password'],
                    created_at,
                    is_active
                )
            )
            conn.commit()
            
            # 返回创建的用户
            return self.get_user_by_id(user_id)
        except Exception as e:
            conn.rollback()
            logger.error(f"创建用户失败: {str(e)}")
            raise
        finally:
            conn.close()
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        更新用户信息
        
        Args:
            user_id (str): 用户ID
            user_data (Dict[str, Any]): 要更新的用户数据
            
        Returns:
            Optional[Dict[str, Any]]: 更新后的用户数据，如果用户不存在则返回None
        """
        # 检查用户是否存在
        existing_user = self.get_user_by_id(user_id)
        if not existing_user:
            return None
        
        # 构建更新字段
        update_fields = []
        params = []
        
        # 可更新的字段
        updatable_fields = ['username', 'email', 'hashed_password', 'is_active']
        
        for field in updatable_fields:
            if field in user_data:
                update_fields.append(f"{field} = ?")
                # 特殊处理布尔值
                if field == 'is_active':
                    params.append(1 if user_data[field] else 0)
                else:
                    params.append(user_data[field])
        
        if not update_fields:
            return existing_user  # 没有要更新的字段
        
        # 添加ID到参数列表
        params.append(user_id)
        
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 如果要更新用户名，检查是否与其他用户冲突
            if 'username' in user_data and user_data['username'] != existing_user['username']:
                cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", 
                              (user_data['username'], user_id))
                if cursor.fetchone():
                    raise ValueError(f"用户名 '{user_data['username']}' 已被其他用户使用")
            
            # 执行更新
            cursor.execute(
                f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?",
                params
            )
            conn.commit()
            
            # 返回更新后的用户
            return self.get_user_by_id(user_id)
        except Exception as e:
            conn.rollback()
            logger.error(f"更新用户失败: {str(e)}")
            raise
        finally:
            conn.close()
    
    def delete_user(self, user_id: str) -> bool:
        """
        删除用户
        
        Args:
            user_id (str): 用户ID
            
        Returns:
            bool: 是否成功删除
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            logger.error(f"删除用户失败: {str(e)}")
            raise
        finally:
            conn.close()
