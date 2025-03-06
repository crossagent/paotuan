from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List, Optional

from web.auth import auth_manager, User, UserCreate, UserLogin, Token

# 创建路由器
router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)

# OAuth2密码流
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/token")

# 依赖函数：获取当前用户
async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """获取当前用户"""
    payload = auth_manager.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    user = auth_manager.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user

# 用户注册
@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register_user(user_create: UserCreate):
    """注册新用户"""
    try:
        user = auth_manager.create_user(user_create)
        token = auth_manager.create_access_token(user)
        return token
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# 用户登录
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户登录获取令牌"""
    user = auth_manager.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_manager.create_access_token(user)
    return token

# 获取当前用户信息
@router.get("/me", response_model=dict)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "created_at": current_user.created_at,
        "is_active": current_user.is_active
    }
