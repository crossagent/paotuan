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

# 全局游戏实例引用
game_instance = None

# 设置游戏实例
def set_game_instance(instance):
    global game_instance
    game_instance = instance

# 获取房间列表
@router.get("/", response_model=List[Dict[str, Any]])
async def list_rooms(current_user: User = Depends(get_current_user)):
    """获取房间列表"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    rooms = []
    for room_id, room in game_instance.rooms.items():
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
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room_name = room_data.get("name", f"{current_user.username}的房间")
    
    # 创建房间
    room_id = str(uuid.uuid4())
    room = GameRoom(id=room_id, name=room_name)
    
    # 添加到游戏实例
    game_instance.rooms[room_id] = room
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 将创建者添加到房间
    player = room_manager.add_player(current_user.id, current_user.username)
    
    logger.info(f"创建房间: {room_name} (ID: {room_id}), 创建者: {current_user.username}")
    
    return {
        "id": room.id,
        "name": room.name,
        "created_at": room.created_at,
        "player_count": len(room.players),
        "has_active_match": room.current_match_id is not None
    }

# 获取房间详情
@router.get("/{room_id}", response_model=Dict[str, Any])
async def get_room(
    room_id: str,
    current_user: User = Depends(get_current_user)
):
    """获取房间详情"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 获取当前游戏局
    current_match = room_manager.get_current_match()
    
    # 获取房主
    host = room_manager.get_host()
    
    # 构建玩家列表
    players = []
    for player in room.players:
        players.append({
            "id": player.id,
            "name": player.name,
            "joined_at": player.joined_at,
            "health": player.health,
            "alive": player.alive,
            "location": player.location,
            "is_ready": player.is_ready,
            "is_host": player.is_host
        })
    
    # 检查是否所有非房主玩家都已准备
    all_ready = room_manager.are_all_players_ready()
    
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
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 将玩家添加到房间
    player = room_manager.add_player(current_user.id, current_user.username)
    
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
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 将玩家从房间中移除
    success, event = room_manager.remove_player(current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="玩家不在房间中"
        )
    
    logger.info(f"玩家离开房间: {current_user.username} (ID: {current_user.id}), 房间: {room.name} (ID: {room_id})")
    
    # 如果返回了事件，发布到事件总线
    if event and game_instance.event_bus:
        await game_instance.event_bus.publish(event)
    
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
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 检查是否是房主
    host = room_manager.get_host()
    if not host or host.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="只有房主可以开始游戏"
        )
    
    # 检查是否所有玩家都已准备
    if not room_manager.are_all_players_ready() and len(room.players) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="还有玩家未准备，无法开始游戏"
        )
    
    # 检查是否有进行中的游戏
    current_match = room_manager.get_current_match()
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
        match = room_manager.create_match(scene)
        
        # 如果指定了剧本，设置剧本
        if scenario_id:
            success = room_manager.set_scenario(scenario_id)
            if not success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"设置剧本失败: {scenario_id}"
                )
        
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
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 获取准备状态
    is_ready = ready_data.get("is_ready", True)
    
    # 检查是否是房主
    host = room_manager.get_host()
    if host and host.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="房主不需要准备"
        )
    
    # 设置准备状态
    success = room_manager.set_player_ready(current_user.id, is_ready)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="设置准备状态失败，玩家可能不在房间中"
        )
    
    # 检查是否所有玩家都已准备
    all_ready = room_manager.are_all_players_ready()
    
    logger.info(f"玩家 {current_user.username} (ID: {current_user.id}) {'准备完毕' if is_ready else '取消准备'}")
    
    return {
        "success": True,
        "is_ready": is_ready,
        "all_players_ready": all_ready
    }

# 踢出玩家
@router.post("/{room_id}/kick/{player_id}", response_model=Dict[str, Any])
async def kick_player(
    room_id: str,
    player_id: str,
    current_user: User = Depends(get_current_user)
):
    """房主踢出玩家"""
    if not game_instance:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="游戏服务器未启动"
        )
    
    room = game_instance.rooms.get(room_id)
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="房间不存在"
        )
    
    # 创建房间管理器
    from core.room import RoomManager
    room_manager = RoomManager(room, game_instance)
    
    # 检查是否是房主
    host = room_manager.get_host()
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
    success, event = room_manager.kick_player(player_id)
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
