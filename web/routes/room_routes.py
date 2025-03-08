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
    if not game_state_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
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
    if not game_state_service or not room_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room_name = room_data.get("name", f"{current_user.username}的房间")
    max_players = room_data.get("max_players", 6)  # 获取最大玩家数，默认为6
    
    # 验证最大玩家数
    if max_players < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="房间最大玩家数不能小于2"
        )
    
    if max_players > 10:  # 设置一个上限
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="房间最大玩家数不能超过10"
        )
    
    # 创建房间
    from core.controllers.room_controller import RoomController
    
    # 使用RoomService创建房间
    room_controller, messages = await room_service.create_room(room_name, current_user.id)
    room = room_controller.room
    
    # 设置最大玩家数
    room.max_players = max_players
    logger.info(f"设置房间最大玩家数: {max_players}")
    
    # 将创建者自动加入房间
    player, _ = await room_service.add_player_to_room(room_controller, current_user.id, current_user.username)
    logger.info(f"创建者 {current_user.username} (ID: {current_user.id}) 自动加入房间")
    
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
    from core.controllers.room_controller import RoomController
    room_controller = RoomController(room)
    
    # 获取当前游戏局
    current_match = None
    if room.current_match_id:
        # 从游戏状态服务获取当前游戏局
        for match in room.matches:
            if match.id == room.current_match_id:
                current_match = match
                break
    
    # 获取房主
    host = room_controller.get_host()
    
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
    all_ready = room_controller.are_all_players_ready()
    
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
    from core.controllers.room_controller import RoomController
    room_controller = RoomController(room)
    
    # 将玩家添加到房间
    player, _ = await room_service.add_player_to_room(room_controller, current_user.id, current_user.username)
    
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
    from core.controllers.room_controller import RoomController
    room_controller = RoomController(room)
    
    # 将玩家从房间中移除
    success, messages = await room_service.remove_player_from_room(room_controller, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="玩家不在房间中"
        )
    
    logger.info(f"玩家离开房间: {current_user.username} (ID: {current_user.id}), 房间: {room.name} (ID: {room_id})")
    
    # 消息已经由room_service处理
    
    return {
        "success": True,
        "message": f"已离开房间: {room.name}"
    }

# 开始游戏
@router.post("/{room_id}/start", response_model=Dict[str, Any])
async def start_game(
    room_id: str,
    game_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """开始游戏"""
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
    from core.controllers.room_controller import RoomController
    room_controller = RoomController(room)
    
    # 检查是否是房主
    host = room_controller.get_host()
    if not host or host.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有房主可以开始游戏"
        )
    
    # 检查是否所有玩家都已准备
    if not room_controller.are_all_players_ready() and len(room.players) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="还有玩家未准备，无法开始游戏"
        )
    
    # 检查是否有进行中的游戏
    current_match = None
    if room.current_match_id:
        # 从游戏状态服务获取当前游戏局
        for match in room.matches:
            if match.id == room.current_match_id:
                current_match = match
                break
    if current_match and current_match.status == GameStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="已有进行中的游戏"
        )
    
    # 获取场景和剧本ID
    scene = game_data.get("scene", "默认场景")
    scenario_id = game_data.get("scenario_id")
    
    try:
        # 创建新游戏局
        from models.entities import Match
        from datetime import datetime
        
        match_id = str(uuid.uuid4())
        match = Match(id=match_id, room_id=room.id, scene=scene, created_at=datetime.now())
        room.matches.append(match)
        room.current_match_id = match_id
        
        # 如果指定了剧本，设置剧本
        if scenario_id:
            from utils.scenario_loader import ScenarioLoader
            scenario_loader = ScenarioLoader()
            scenario = scenario_loader.load_scenario(scenario_id)
            if not scenario:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"剧本不存在: {scenario_id}"
                )
            match.scenario_id = scenario_id
        
        # 更新游戏状态
        match.status = GameStatus.RUNNING
        
        # 重置所有玩家的准备状态
        for player in room.players:
            player.is_ready = False
        
        logger.info(f"开始游戏: 房间={room.name} (ID: {room_id}), 场景={scene}, 剧本ID={scenario_id}")
        
        return {
            "match_id": match.id,
            "status": match.status,
            "scene": match.scene,
            "scenario_id": match.scenario_id
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# 设置玩家准备状态
@router.post("/{room_id}/ready", response_model=Dict[str, Any])
async def set_player_ready(
    room_id: str,
    ready_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """设置玩家准备状态"""
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
    from core.controllers.room_controller import RoomController
    room_controller = RoomController(room)
    
    # 获取准备状态
    is_ready = ready_data.get("is_ready", True)
    
    # 检查是否是房主
    host = room_controller.get_host()
    if host and host.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="房主不需要准备"
        )
    
    # 设置准备状态
    success, _ = await room_service.set_player_ready(room_controller, current_user.id, is_ready)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="设置准备状态失败，玩家可能不在房间中"
        )
    
    # 检查是否所有玩家都已准备
    all_ready = room_controller.are_all_players_ready()
    
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
    from core.controllers.room_controller import RoomController
    room_controller = RoomController(room)
    
    # 获取角色名称
    character_name = character_data.get("character_name")
    if not character_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="角色名称不能为空"
        )
    
    # 获取当前游戏局
    current_match = None
    if room.current_match_id:
        # 从游戏状态服务获取当前游戏局
        for match in room.matches:
            if match.id == room.current_match_id:
                current_match = match
                break
    
    if not current_match:
        success, message = False, "没有进行中的游戏"
    else:
        # 查找或创建角色
        character = next((c for c in current_match.characters if c.name == character_name), None)
        if not character:
            # 创建新角色
            from models.entities import Character
            character_id = str(uuid.uuid4())
            character = Character(id=character_id, name=character_name, match_id=current_match.id)
            current_match.characters.append(character)
        
        # 设置玩家角色
        success, _ = await room_service.set_player_character(room_controller, current_user.id, character.id)
        message = f"已选择角色: {character_name}" if success else "选择角色失败"
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message
        )
    
    logger.info(f"玩家 {current_user.username} (ID: {current_user.id}) 选择了角色: {character_name}")
    
    return {
        "success": True,
        "message": message,
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
    from core.controllers.room_controller import RoomController
    room_controller = RoomController(room)
    
    # 检查是否是房主
    host = room_controller.get_host()
    if not host or host.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有房主可以设置剧本"
        )
    
    # 获取剧本ID
    scenario_id = scenario_data.get("scenario_id")
    if not scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="剧本ID不能为空"
        )
    
    # 检查剧本是否存在
    from utils.scenario_loader import ScenarioLoader
    scenario_loader = ScenarioLoader()
    scenario = scenario_loader.load_scenario(scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"剧本不存在: {scenario_id}"
        )
    
    # 获取当前游戏局
    current_match = None
    if room.current_match_id:
        # 从游戏状态服务获取当前游戏局
        for match in room.matches:
            if match.id == room.current_match_id:
                current_match = match
                break
    
    if not current_match:
        success, error_msg = False, "没有进行中的游戏"
    else:
        # 设置剧本
        current_match.scenario_id = scenario_id
        success, error_msg = True, None
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg or "设置剧本失败"
        )
    
    logger.info(f"房主 {current_user.username} (ID: {current_user.id}) 设置了剧本: {scenario_id}")
    
    return {
        "success": True,
        "message": f"已设置剧本: {scenario.name}",
        "scenario": {
            "id": scenario_id,
            "name": scenario.name,
            "description": scenario.description
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
    from core.controllers.room_controller import RoomController
    room_controller = RoomController(room)
    
    # 检查是否是房主
    host = room_controller.get_host()
    if not host or host.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有房主可以踢出玩家"
        )
    
    # 不能踢出自己
    if player_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能踢出自己"
        )
    
    # 踢出玩家
    success, _ = await room_service.kick_player(room_controller, current_user.id, player_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="踢出玩家失败，玩家可能不在房间中或是房主"
        )
    
    logger.info(f"房主 {current_user.username} (ID: {current_user.id}) 踢出玩家 (ID: {player_id})")
    
    return {
        "success": True,
        "message": "玩家已被踢出"
    }
