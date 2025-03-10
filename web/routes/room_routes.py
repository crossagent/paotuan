from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
import uuid
import logging

from web.routes.user_routes import get_current_user
from web.auth import User
from models.entities import Room as GameRoom, GameStatus

# 创建路由器
router = APIRouter(
    prefix="/api/rooms",
    tags=["rooms"],
    responses={404: {"description": "Not found"}},
)

# 配置日志
logger = logging.getLogger(__name__)

# 房间数据模型
class RoomInfo:
    """房间信息模型"""
    def __init__(self, room: GameRoom):
        self.id = room.id
        self.name = room.name
        self.created_at = room.created_at
        self.player_count = len(room.players)
        self.has_active_match = room.current_match_id is not None
        self.settings = room.settings

# 全局服务引用
game_state_service = None
room_service = None
event_bus = None

# 设置游戏状态
def set_game_state(game_state):
    global game_state_service, room_service, event_bus
    from services.game_state_service import GameStateService
    from services.room_service import RoomService
    from core.events import EventBus
    
    # 创建服务
    event_bus = EventBus()
    game_state_service = GameStateService(game_state, event_bus)
    room_service = RoomService(game_state_service, event_bus)

# 获取房间列表
@router.get("/", response_model=List[Dict[str, Any]])
async def list_rooms(current_user: User = Depends(get_current_user)):
    """获取房间列表"""
    # 使用ListRoomsCommand
    from adapters.base import ListRoomsEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = ListRoomsEvent(current_user.id)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 由于ListRoomsCommand返回的是消息格式，需要转换为API响应格式
    rooms = []
    for room in game_state_service.list_rooms():
        room_info = RoomInfo(room)
        rooms.append({
            "id": room_info.id,
            "name": room_info.name,
            "created_at": room_info.created_at,
            "player_count": room_info.player_count,
            "has_active_match": room_info.has_active_match
        })
    
    return rooms

# 创建房间
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_room(
    room_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """创建新房间"""
    # 使用CreateRoomCommand
    from adapters.base import CreateRoomEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 获取房间名称
    room_name = room_data.get("name", f"{current_user.username}的房间")
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = CreateRoomEvent(current_user.id, room_name)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 由于CreateRoomCommand返回的是消息格式，需要转换为API响应格式
    # 这里我们需要从game_state_service获取新创建的房间
    
    # 获取所有房间
    rooms = game_state_service.list_rooms()
    
    # 找到最新创建的房间（假设是最后一个）
    room = rooms[-1] if rooms else None
    
    if not room:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建房间失败"
        )
    
    # 设置最大玩家数
    max_players = room_data.get("max_players", 6)  # 获取最大玩家数，默认为6
    room.max_players = max_players
    logger.info(f"设置房间最大玩家数: {max_players}")
    
    # 将创建者自动加入房间
    from adapters.base import JoinRoomEvent
    join_event = JoinRoomEvent(current_user.id, current_user.username, room.id)
    join_command = command_factory.create_command(join_event.event_type)
    join_result = await join_command.execute(join_event)
    
    logger.info(f"创建房间: {room_name} (ID: {room.id}), 最大玩家数: {max_players}, 创建者: {current_user.username}")
    
    return {
        "id": room.id,
        "name": room.name,
        "created_at": room.created_at,
        "player_count": len(room.players),
        "max_players": room.max_players,
        "has_active_match": room.current_match_id is not None
    }

# 获取房间详情
@router.get("/{room_id}", response_model=Dict[str, Any])
async def get_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取房间详情"""
    if not game_state_service or not room_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_state_service.get_room(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间控制器
    from core.contexts.room_context import RoomContext
    room_context = RoomContext(room)
    
    # 获取当前游戏局
    current_match = None
    if room.current_match_id:
        # 从游戏状态服务获取当前游戏局
        for match in room.matches:
            if match.id == room.current_match_id:
                current_match = match
                break
    
    # 获取房主
    host = room_context.get_host()
    
    # 构建玩家列表
    players = []
    for player in room.players:
        player_info = {
            "id": player.id,
            "name": player.name,
            "joined_at": player.joined_at,
            "is_ready": player.is_ready,
            "is_host": player.is_host,
            "character_id": player.character_id
        }
        
        # 如果有关联的角色，添加角色信息
        if current_match and player.character_id:
            character = next((c for c in current_match.characters if c.id == player.character_id), None)
            if character:
                player_info.update({
                    "health": character.health,
                    "alive": character.alive,
                    "location": character.location
                })
        
        players.append(player_info)
    
    # 检查是否所有非房主玩家都已准备
    all_ready = room_context.are_all_players_ready()
    
    return {
        "id": room.id,
        "name": room.name,
        "created_at": room.created_at,
        "players": players,
        "host_id": room.host_id,
        "all_players_ready": all_ready,
        "current_match": {
            "id": current_match.id,
            "status": current_match.status,
            "scene": current_match.scene,
            "created_at": current_match.created_at,
            "scenario_id": current_match.scenario_id
        } if current_match else None,
        "settings": room.settings
    }

# 加入房间
@router.post("/{room_id}/join", response_model=Dict[str, Any])
async def join_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    """加入房间"""
    # 使用JoinRoomCommand
    from adapters.base import JoinRoomEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = JoinRoomEvent(current_user.id, current_user.username, room_id)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 由于JoinRoomCommand返回的是消息格式，需要转换为API响应格式
    # 获取房间
    room = game_state_service.get_room(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 获取玩家
    player = next((p for p in room.players if p.id == current_user.id), None)
    if not player:
        # 如果玩家不在房间中，可能是加入失败
        error_message = result[0]["content"] if result else "加入房间失败"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    logger.info(f"玩家加入房间: {current_user.username} (ID: {current_user.id}), 房间: {room.name} (ID: {room_id})")
    
    return {
        "id": room.id,
        "name": room.name,
        "player": {
            "id": player.id,
            "name": player.name
        }
    }

# 离开房间
@router.post("/{room_id}/leave", response_model=Dict[str, Any])
async def leave_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    """离开房间"""
    # 使用LeaveRoomCommand
    from adapters.base import PlayerLeftEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 获取房间名称（用于日志和返回消息）
    room_name = ""
    room = game_state_service.get_room(room_id)
    if room:
        room_name = room.name
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = PlayerLeftEvent(current_user.id, current_user.username, room_id)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    logger.info(f"玩家离开房间: {current_user.username} (ID: {current_user.id}), 房间: {room_name} (ID: {room_id})")
    
    return {
        "success": True,
        "message": f"已离开房间: {room_name}"
    }

# 开始游戏
@router.post("/{room_id}/start", response_model=Dict[str, Any])
async def start_game(
    room_id: str,
    game_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """开始游戏"""
    # 使用StartMatchCommand
    from adapters.base import StartMatchEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = StartMatchEvent(current_user.id, current_user.username)
    # 添加额外数据
    event.data["room_id"] = room_id
    event.data["scene"] = game_data.get("scene", "默认场景")
    event.data["scenario_id"] = game_data.get("scenario_id")
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 检查是否成功
    success_message = next((msg for msg in result if msg.get("recipient") == current_user.id), None)
    if not success_message or "游戏已开始" not in success_message.get("content", ""):
        error_message = success_message.get("content") if success_message else "开始游戏失败"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    # 获取当前游戏局
    room = game_state_service.get_room(room_id)
    if not room or not room.current_match_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取游戏局失败"
        )
    
    current_match = next((m for m in room.matches if m.id == room.current_match_id), None)
    if not current_match:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取游戏局失败"
        )
    
    logger.info(f"开始游戏: 房间={room.name} (ID: {room_id}), 场景={current_match.scene}, 剧本ID={current_match.scenario_id}")
    
    return {
        "match_id": current_match.id,
        "status": current_match.status,
        "scene": current_match.scene,
        "scenario_id": current_match.scenario_id
    }

# 设置玩家准备状态
@router.post("/{room_id}/ready", response_model=Dict[str, Any])
async def set_player_ready(
    room_id: str,
    ready_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """设置玩家准备状态"""
    # 使用SetPlayerReadyCommand
    from adapters.base import SetPlayerReadyEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 获取准备状态
    is_ready = ready_data.get("is_ready", True)
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = SetPlayerReadyEvent(current_user.id, room_id, is_ready)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 获取房间
    room = game_state_service.get_room(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间控制器
    from core.contexts.room_context import RoomContext
    room_context = RoomContext(room)
    
    # 检查是否所有玩家都已准备
    all_ready = room_context.are_all_players_ready()
    
    logger.info(f"玩家 {current_user.username} (ID: {current_user.id}) {'准备完毕' if is_ready else '取消准备'}")
    
    return {
        "success": True,
        "is_ready": is_ready,
        "all_players_ready": all_ready
    }

# 选择角色
@router.post("/{room_id}/select_character", response_model=Dict[str, Any])
async def select_character(
    room_id: str,
    character_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """选择角色"""
    # 使用SelectCharacterCommand
    from adapters.base import SelectCharacterEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 获取角色名称
    character_name = character_data.get("character_name")
    if not character_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色名称不能为空"
        )
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = SelectCharacterEvent(current_user.id, character_name)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 检查是否成功
    success_message = next((msg for msg in result if msg.get("recipient") == current_user.id), None)
    if not success_message or "已选择角色" not in success_message.get("content", ""):
        error_message = success_message.get("content") if success_message else "选择角色失败"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    logger.info(f"玩家 {current_user.username} (ID: {current_user.id}) 选择了角色: {character_name}")
    
    return {
        "success": True,
        "message": f"已选择角色: {character_name}",
        "character_name": character_name
    }

# 设置剧本
@router.post("/{room_id}/set_scenario", response_model=Dict[str, Any])
async def set_scenario(
    room_id: str,
    scenario_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """设置剧本"""
    # 使用SetScenarioCommand
    from adapters.base import SetScenarioEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 获取剧本ID
    scenario_id = scenario_data.get("scenario_id")
    if not scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="剧本ID不能为空"
        )
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = SetScenarioEvent(current_user.id, scenario_id)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 检查是否成功
    success_message = next((msg for msg in result if msg.get("recipient") == current_user.id), None)
    if not success_message or "已设置剧本" not in success_message.get("content", ""):
        error_message = success_message.get("content") if success_message else "设置剧本失败"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    # 获取剧本名称
    from utils.scenario_loader import ScenarioLoader
    scenario_loader = ScenarioLoader()
    scenario = scenario_loader.load_scenario(scenario_id)
    scenario_name = scenario.name if scenario else "未知剧本"
    
    logger.info(f"房主 {current_user.username} (ID: {current_user.id}) 设置了剧本: {scenario_id}")
    
    return {
        "success": True,
        "message": f"已设置剧本: {scenario_name}",
        "scenario": {
            "id": scenario_id,
            "name": scenario_name
        }
    }

# 踢出玩家
@router.post("/{room_id}/kick/{player_id}", response_model=Dict[str, Any])
async def kick_player(
    room_id: str,
    player_id: str,
    current_user: User = Depends(get_current_user)
):
    """房主踢出玩家"""
    # 使用KickPlayerCommand
    from adapters.base import KickPlayerEvent
    from services.commands.factory import CommandFactory
    from core.rules import RuleEngine
    
    # 创建命令工厂
    command_factory = CommandFactory(
        game_state_service.game_state, 
        event_bus, 
        None,  # AI服务暂时不需要
        RuleEngine()  # 创建规则引擎实例
    )
    
    # 创建事件
    event = KickPlayerEvent(current_user.id, player_id, room_id)
    
    # 获取命令
    command = command_factory.create_command(event.event_type)
    
    # 执行命令
    result = await command.execute(event)
    
    # 处理结果
    # 检查是否成功
    success_message = next((msg for msg in result if msg.get("recipient") == current_user.id), None)
    if not success_message or "已将玩家踢出房间" not in success_message.get("content", ""):
        error_message = success_message.get("content") if success_message else "踢出玩家失败"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )
    
    logger.info(f"房主 {current_user.username} (ID: {current_user.id}) 踢出玩家 (ID: {player_id})")
    
    return {
        "success": True,
        "message": "玩家已被踢出"
    }
