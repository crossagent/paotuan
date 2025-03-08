import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from passlib.context import CryptContext
from pydantic import BaseModel
import uuid
import logging
import os
from pathlib import Path
from persistence.user_repository import UserRepository

# 配置日志
logger = logging.getLogger(__name__)

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT配置
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key-for-jwt")  # 生产环境应使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# 确保数据目录存在
Path("web/data").mkdir(parents=True, exist_ok=True)

# 用户模型
class User(BaseModel):
    id: str
    username: str
    email: str
    hashed_password: str
    created_at: datetime = datetime.now()
    is_active: bool = True

# 令牌模型
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str

# 用户创建模型
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# 用户登录模型
class UserLogin(BaseModel):
    username: str
    password: str

class AuthManager:
    """认证管理器"""
    
    def __init__(self):
        # 初始化用户仓库
        self.user_repository = UserRepository()
        # 尝试迁移现有JSON数据到SQLite
        self._migrate_data_if_needed()
    
    def _migrate_data_if_needed(self) -> None:
        """如果需要，将JSON数据迁移到SQLite"""
        try:
            self.user_repository.migrate_from_json()
            logger.info("用户数据迁移检查完成")
        except Exception as e:
            logger.error(f"迁移用户数据失败: {str(e)}")
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        user_data = self.user_repository.get_user_by_username(username)
        if user_data:
            return User(**user_data)
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        user_data = self.user_repository.get_user_by_id(user_id)
        if user_data:
            return User(**user_data)
        return None
    
    def create_user(self, user_create: UserCreate) -> User:
        """创建新用户"""
        # 哈希密码
        hashed_password = pwd_context.hash(user_create.password)
        
        # 准备用户数据
        user_data = {
            "id": str(uuid.uuid4()),
            "username": user_create.username,
            "email": user_create.email,
            "hashed_password": hashed_password,
            "created_at": datetime.now().isoformat(),
            "is_active": True
        }
        
        # 创建用户
        try:
            created_user_data = self.user_repository.create_user(user_data)
            user = User(**created_user_data)
            logger.info(f"创建新用户: {user.username} (ID: {user.id})")
            return user
        except ValueError as e:
            # 重新抛出异常，保持与原有API一致
            raise ValueError(str(e))
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """验证用户"""
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not pwd_context.verify(password, user.hashed_password):
            return None
        return user
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> Optional[User]:
        """
        更新用户信息
        
        Args:
            user_id (str): 用户ID
            user_data (Dict[str, Any]): 要更新的用户数据
            
        Returns:
            Optional[User]: 更新后的用户，如果用户不存在则返回None
        """
        # 如果包含密码字段，需要哈希处理
        if 'password' in user_data:
            user_data['hashed_password'] = pwd_context.hash(user_data.pop('password'))
        
        try:
            updated_user_data = self.user_repository.update_user(user_id, user_data)
            if updated_user_data:
                return User(**updated_user_data)
            return None
        except ValueError as e:
            # 重新抛出异常，保持与原有API一致
            raise ValueError(str(e))
    
    def delete_user(self, user_id: str) -> bool:
        """
        删除用户
        
        Args:
            user_id (str): 用户ID
            
        Returns:
            bool: 是否成功删除
        """
        return self.user_repository.delete_user(user_id)
    
    def create_access_token(self, user: User) -> Token:
        """创建访问令牌"""
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + expires_delta
        
        to_encode = {
            "sub": user.id,
            "username": user.username,
            "exp": expire
        }
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        
        return Token(
            access_token=encoded_jwt,
            token_type="bearer",
            user_id=user.id,
            username=user.username
        )
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """验证令牌"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if user_id is None:
                return None
                
            # 检查用户是否存在
            user = self.get_user_by_id(user_id)
            if not user:
                return None
                
            return payload
        except jwt.PyJWTError:
            return None

# 创建认证管理器实例
auth_manager = AuthManager()
