from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
import logging
import json
import asyncio

from web.routes.user_routes import get_current_user
from web.auth import User, auth_manager
from adapters.web_adapter import WebAdapter
from adapters.base import StartMatchEvent, EndMatchEvent

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
    
    # 使用CharacterActionCommand
    from adapters.base import PlayerActionEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 创建命令工厂
    command_factory = CommandFactory(
        web_adapter.game_state,
        web_adapter.event_bus,
        web_adapter.ai_service,
        RuleEngine()
    )
    
    # 创建事件
    event = PlayerActionEvent(current_user.id, action_text)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 检查是否成功
    success_message = next((msg for msg in result if msg.get("recipient") == current_user.id), None)
    if not success_message:
        # 如果没有特定的成功消息，我们认为操作成功
        return {
            "success": True,
            "message": "行动已提交"
        }
    else:
        # 返回实际的结果消息
        return {
            "success": True,
            "message": success_message.get("content", "行动已提交")
        }

# 获取可用剧本列表
@router.get("/scenarios", response_model=List[Dict[str, Any]])
async def list_scenarios(current_user: User = Depends(get_current_user)):
    """获取可用剧本列表"""
    if not web_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    # 使用ListScenariosCommand
    from adapters.base import ListScenariosEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 创建命令工厂
    command_factory = CommandFactory(
        web_adapter.game_state,
        web_adapter.event_bus,
        web_adapter.ai_service,
        RuleEngine()
    )
    
    # 创建事件
    event = ListScenariosEvent(current_user.id)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 检查是否成功
    success_message = next((msg for msg in result if msg.get("recipient") == current_user.id), None)
    if not success_message:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取剧本列表失败"
        )
    
    # 返回剧本列表
    scenarios = success_message.get("content", [])
    return scenarios

# 获取剧本详情
@router.get("/scenarios/{scenario_id}", response_model=Dict[str, Any])
async def get_scenario(
    scenario_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取剧本详情"""
    if not web_adapter:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    # 使用GetScenarioCommand
    from adapters.base import GetScenarioEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 创建命令工厂
    command_factory = CommandFactory(
        web_adapter.game_state,
        web_adapter.event_bus,
        web_adapter.ai_service,
        RuleEngine()
    )
    
    # 创建事件
    event = GetScenarioEvent(current_user.id, scenario_id)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 检查是否成功
    success_message = next((msg for msg in result if msg.get("recipient") == current_user.id), None)
    if not success_message:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取剧本详情失败"
        )
    
    # 检查是否有错误消息
    content = success_message.get("content", {})
    if isinstance(content, str) and "剧本不存在" in content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=content
        )
    
    # 返回剧本详情
    return content

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
