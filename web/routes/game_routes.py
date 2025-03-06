from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
import logging
import json
import asyncio

from web.routes.user_routes import get_current_user
from web.auth import User, auth_manager
from adapters.web_adapter import WebAdapter

# 创建路由器
router = APIRouter(
    prefix="/api/game",
    tags=["game"],
    responses={404: {"description": "Not found"}},
)

# 配置日志
logger = logging.getLogger(__name__)

# 全局Web适配器引用
web_adapter = None

# 设置Web适配器
def set_web_adapter(adapter: WebAdapter):
    global web_adapter
    web_adapter = adapter

# 获取游戏状态
@router.get("/state", response_model=Dict[str, Any])
async def get_game_state(current_user: User = Depends(get_current_user)):
    """获取游戏状态"""
    if not web_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    # 从web_adapter.game_instance获取游戏状态
    # 这里需要根据实际情况修改
    return {
        "status": "running",
        "player_count": len(web_adapter.connected_clients),
        "room_count": 0  # 需要从游戏实例获取
    }

# 发送游戏行动
@router.post("/action", response_model=Dict[str, Any])
async def send_action(
    action_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """发送游戏行动"""
    if not web_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    action_text = action_data.get("action", "")
    if not action_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="行动内容不能为空"
        )
    
    # 处理行动
    await web_adapter.handle_message(current_user.id, current_user.username, action_text)
    
    return {
        "success": True,
        "message": "行动已提交"
    }

# 获取可用剧本列表
@router.get("/scenarios", response_model=List[Dict[str, Any]])
async def list_scenarios(current_user: User = Depends(get_current_user)):
    """获取可用剧本列表"""
    try:
        # 加载剧本
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenarios = scenario_loader.list_scenarios()
        
        result = []
        for scenario_id, scenario in scenarios.items():
            result.append({
                "id": scenario_id,
                "name": scenario.name,
                "description": scenario.description,
                "player_count": scenario.player_count
            })
        
        return result
    except Exception as e:
        logger.error(f"获取剧本列表失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取剧本列表失败: {str(e)}"
        )

# 获取剧本详情
@router.get("/scenarios/{scenario_id}", response_model=Dict[str, Any])
async def get_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取剧本详情"""
    try:
        # 加载剧本
        from utils.scenario_loader import ScenarioLoader
        scenario_loader = ScenarioLoader()
        scenario = scenario_loader.load_scenario(scenario_id)
        
        if not scenario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"剧本不存在: {scenario_id}"
            )
        
        # 构建场景列表
        scenes = []
        for scene in scenario.scenes:
            scenes.append({
                "name": scene.name,
                "description": scene.description
            })
        
        return {
            "id": scenario_id,
            "name": scenario.name,
            "description": scenario.description,
            "player_count": scenario.player_count,
            "main_scene": scenario.main_scene,
            "scenes": scenes
        }
    except Exception as e:
        logger.error(f"获取剧本详情失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取剧本详情失败: {str(e)}"
        )

# WebSocket连接
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    await websocket.accept()
    
    if not web_adapter:
        await websocket.close(code=1011, reason="游戏服务器未启动")
        return
    
    try:
        # 等待认证消息
        auth_message = await websocket.receive_text()
        auth_data = json.loads(auth_message)
        
        if "token" not in auth_data:
            await websocket.close(code=1008, reason="未提供认证令牌")
            return
        
        # 验证令牌
        token = auth_data["token"]
        payload = auth_manager.verify_token(token)
        if not payload:
            await websocket.close(code=1008, reason="无效的认证令牌")
            return
        
        # 获取用户信息
        user_id = payload.get("sub")
        username = payload.get("username")
        
        # 注册WebSocket客户端
        connection = await web_adapter.register_client(user_id, username, websocket)
        
        # 处理WebSocket连接
        await connection.handle()
    except WebSocketDisconnect:
        logger.info("WebSocket连接断开")
    except Exception as e:
        logger.exception(f"WebSocket连接异常: {str(e)}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass
