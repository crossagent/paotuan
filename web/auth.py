import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from passlib.context import CryptContext
from pydantic import BaseModel
import uuid
import logging
import json
import os
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT配置
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "your-secret-key-for-jwt")  # 生产环境应使用环境变量
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# 用户数据文件路径
USER_DATA_FILE = "web/data/users.json"

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
        self.users: Dict[str, User] = {}
        self.load_users()
    
    def load_users(self) -> None:
        """从文件加载用户数据"""
        try:
            if os.path.exists(USER_DATA_FILE):
                with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    user_data = json.load(f)
                    for user_dict in user_data:
                        user = User(**user_dict)
                        self.users[user.id] = user
                logger.info(f"已加载 {len(self.users)} 个用户")
            else:
                logger.info("用户数据文件不存在，将创建新文件")
                self.save_users()
        except Exception as e:
            logger.error(f"加载用户数据失败: {str(e)}")
    
    def save_users(self) -> None:
        """保存用户数据到文件"""
        try:
            user_data = [user.dict() for user in self.users.values()]
            with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, ensure_ascii=False, default=str)
            logger.info(f"已保存 {len(self.users)} 个用户")
        except Exception as e:
            logger.error(f"保存用户数据失败: {str(e)}")
    
    def get_user_by_username(self, username: str) -> Optional[User]:
        """通过用户名获取用户"""
        for user in self.users.values():
            if user.username == username:
                return user
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """通过ID获取用户"""
        return self.users.get(user_id)
    
    def create_user(self, user_create: UserCreate) -> User:
        """创建新用户"""
        # 检查用户名是否已存在
        if self.get_user_by_username(user_create.username):
            raise ValueError(f"用户名 '{user_create.username}' 已存在")
            
        # 创建用户
        user_id = str(uuid.uuid4())
        hashed_password = pwd_context.hash(user_create.password)
        
        user = User(
            id=user_id,
            username=user_create.username,
            email=user_create.email,
            hashed_password=hashed_password
        )
        
        # 保存用户
        self.users[user_id] = user
        self.save_users()
        
        logger.info(f"创建新用户: {user.username} (ID: {user.id})")
        return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """验证用户"""
        user = self.get_user_by_username(username)
        if not user:
            return None
        if not pwd_context.verify(password, user.hashed_password):
            return None
        return user
    
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
